from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from purchases.models import Purchase
from services.purchase_tree_report_service import PurchaseTreeReportService

User = get_user_model()


class PurchaseTreeReportServiceTest(TestCase):
    def test_closed_without_order_number(self):
        purchase = Purchase(
            purchase_number='8001',
            line_number=1,
            product_title='کالا',
            quantity=1,
            unit='عدد',
            status='بسته شده',
            order_total=100,
            invoice_total=100,
        )
        self.assertEqual(
            PurchaseTreeReportService.classify_leaf(purchase),
            'closed_no_order',
        )

    def test_closed_with_stopped_order(self):
        purchase = Purchase(
            purchase_number='8002',
            line_number=1,
            product_title='کالا',
            quantity=1,
            unit='عدد',
            status='بسته شده',
            order_request_number='19902',
            order_request_status='متوقف شده',
        )
        self.assertEqual(
            PurchaseTreeReportService.classify_leaf(purchase),
            'closed_with_order_stopped',
        )

    def test_open_without_preinvoice_or_order(self):
        purchase = Purchase(
            purchase_number='8003',
            line_number=1,
            product_title='کالا',
            quantity=1,
            unit='عدد',
            status='در جریان',
            inquiry_number='INQ-1',
        )
        self.assertEqual(
            PurchaseTreeReportService.classify_leaf(purchase),
            'open_has_inquiry_no_preinvoice',
        )

    def test_build_tree_counts(self):
        Purchase.objects.create(
            purchase_number='8010',
            line_number=1,
            product_title='بسته بدون سفارش',
            quantity=1,
            unit='عدد',
            status='بسته شده',
        )
        Purchase.objects.create(
            purchase_number='8011',
            line_number=1,
            product_title='باز با استعلام',
            quantity=1,
            unit='عدد',
            status='در جریان',
            inquiry_number='INQ-8011',
        )

        summary = PurchaseTreeReportService.build_tree(Purchase.objects.all())
        self.assertEqual(summary['total'], 2)
        self.assertEqual(summary['counts']['closed_no_order'], 1)
        self.assertEqual(summary['counts']['open_has_inquiry_no_preinvoice'], 1)
        self.assertGreater(summary['tree']['value'], 0)

    def test_build_graph_nodes_and_links(self):
        Purchase.objects.create(
            purchase_number='8020',
            line_number=1,
            product_title='بسته',
            quantity=1,
            unit='عدد',
            status='بسته شده',
        )
        Purchase.objects.create(
            purchase_number='8021',
            line_number=1,
            product_title='باز',
            quantity=1,
            unit='عدد',
            status='در جریان',
            inquiry_number='INQ-8021',
        )

        graph = PurchaseTreeReportService.build_graph(Purchase.objects.all())
        self.assertEqual(graph['total'], 2)
        self.assertGreaterEqual(len(graph['nodes']), 3)
        self.assertGreaterEqual(len(graph['links']), 2)

        root = next(n for n in graph['nodes'] if n['id'] == 'all')
        self.assertEqual(root['value'], 2)
        self.assertIn('px', root)
        self.assertIn('py', root)
        self.assertIn('source', graph['links'][0])
        self.assertIn('target', graph['links'][0])
        self.assertIn('x1', graph['links'][0])

    def test_get_node_purchases_for_branch_and_leaf(self):
        Purchase.objects.create(
            purchase_number='8040',
            line_number=1,
            product_title='بسته',
            quantity=1,
            unit='عدد',
            status='بسته شده',
        )
        Purchase.objects.create(
            purchase_number='8041',
            line_number=1,
            product_title='باز',
            quantity=1,
            unit='عدد',
            status='در جریان',
            inquiry_number='INQ-8041',
        )
        qs = Purchase.objects.filter(purchase_number__in=['8040', '8041'])

        closed_rows = PurchaseTreeReportService.get_node_purchases(qs, 'closed')
        self.assertEqual(len(closed_rows), 1)
        self.assertEqual(closed_rows[0]['purchase_number'], '8040')

        leaf_rows = PurchaseTreeReportService.get_node_purchases(qs, 'open_has_inquiry_no_preinvoice')
        self.assertEqual(len(leaf_rows), 1)
        self.assertEqual(leaf_rows[0]['purchase_number'], '8041')

        all_rows = PurchaseTreeReportService.get_node_purchases(qs, 'all')
        self.assertEqual(len(all_rows), 2)

    def test_purchase_tree_page_renders_svg_graph(self):
        user = User.objects.create_user(
            username='graph_admin',
            email='graph@test.local',
            password='pass',
            role='admin',
        )
        Purchase.objects.create(
            purchase_number='8030',
            line_number=1,
            product_title='تست گراف',
            quantity=1,
            unit='عدد',
            status='در جریان',
        )
        client = Client()
        client.force_login(user)
        response = client.get('/reports/purchase-tree/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('<svg id="purchaseTreeChart"', html)
        self.assertIn('<line ', html)
        self.assertIn('<circle ', html)
        self.assertNotIn('echarts.min.js', html)

    def test_get_node_purchases_page_paginates(self):
        for i in range(5):
            Purchase.objects.create(
                purchase_number=f'806{i}',
                line_number=1,
                product_title=f'بسته {i}',
                quantity=1,
                unit='عدد',
                status='بسته شده',
            )
        qs = Purchase.objects.filter(purchase_number__startswith='806')

        page1, total = PurchaseTreeReportService.get_node_purchases_page(
            qs, 'closed_no_order', offset=0, limit=2,
        )
        page2, total2 = PurchaseTreeReportService.get_node_purchases_page(
            qs, 'closed_no_order', offset=2, limit=2,
        )
        self.assertEqual(total, 5)
        self.assertEqual(total2, 5)
        self.assertEqual(len(page1), 2)
        self.assertEqual(len(page2), 2)
        self.assertNotEqual(page1[0]['purchase_number'], page2[0]['purchase_number'])

    def test_purchase_tree_page_shows_node_details(self):
        user = User.objects.create_user(
            username='graph_detail_admin',
            email='graphdetail@test.local',
            password='pass',
            role='admin',
        )
        Purchase.objects.create(
            purchase_number='8050',
            line_number=1,
            product_title='جزئیات گراف',
            quantity=1,
            unit='عدد',
            status='بسته شده',
        )
        client = Client()
        client.force_login(user)
        response = client.get('/reports/purchase-tree/?node=closed_no_order')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('جزئیات گراف', html)
        self.assertIn('graph-node-link is-selected', html)
        self.assertIn('بسته شده — بدون شماره سفارش', html)
        self.assertIn('از', html)

    def test_purchase_tree_page_pagination_links(self):
        user = User.objects.create_user(
            username='graph_page_admin',
            email='graphpage@test.local',
            password='pass',
            role='admin',
        )
        for i in range(3):
            Purchase.objects.create(
                purchase_number=f'807{i}',
                line_number=1,
                product_title=f'صفحه {i}',
                quantity=1,
                unit='عدد',
                status='بسته شده',
            )
        client = Client()
        client.force_login(user)
        response = client.get('/reports/purchase-tree/?node=closed_no_order&page=1')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('node=closed_no_order', html)
        self.assertIn('نمایش', html)
        self.assertIn('از', html)