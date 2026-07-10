"""گزارش درختی وضعیت درخواست‌های خرید"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

from purchases.models import Purchase, is_valid_value


class PurchaseTreeReportService:
    ROOT_ID = 'all'

    LEAF_META = {
        'closed_no_order': {
            'label': 'بسته شده — بدون شماره سفارش',
            'hint': 'وضعیت اکسل «بسته شده» ولی ستون شماره سفارش خالی است',
        },
        'closed_with_order_stopped': {
            'label': 'بسته شده — سفارش متوقف',
            'hint': 'بسته شده با شماره سفارش و وضعیت توقف/لغو',
        },
        'closed_with_order_done': {
            'label': 'بسته شده — پرداخت یا تحویل',
            'hint': 'بسته شده، سفارش دارد و به پرداخت/تحویل رسیده',
        },
        'closed_with_order_payment': {
            'label': 'بسته شده — در انتظار پرداخت',
            'hint': 'بسته شده با سفارش و درخواست پرداخت',
        },
        'closed_with_order_other': {
            'label': 'بسته شده — سایر (با سفارش)',
            'hint': 'بسته شده با شماره سفارش — سایر وضعیت‌های گردش کار',
        },
        'open_has_order': {
            'label': 'باز — دارای سفارش',
            'hint': 'در جریان و شماره سفارش ثبت شده',
        },
        'open_has_order_cmd_no_order': {
            'label': 'باز — دستور خرید، بدون سفارش',
            'hint': 'دستور خرید صادر شده ولی شماره سفارش ندارد',
        },
        'open_has_preinvoice_no_cmd': {
            'label': 'باز — پیش‌فاکتور، بدون دستور',
            'hint': 'پیش‌فاکتور دارد ولی دستور خرید ندارد',
        },
        'open_has_inquiry_no_preinvoice': {
            'label': 'باز — استعلام، بدون پیش‌فاکتور',
            'hint': 'استعلام دارد ولی پیش‌فاکتور ندارد',
        },
        'open_no_inquiry': {
            'label': 'باز — بدون استعلام',
            'hint': 'هنوز استعلام صادر نشده',
        },
    }

    TREE_BRANCHES = (
        {
            'id': 'closed',
            'label': 'بسته شده',
            'children': (
                {'id': 'closed_no_order', 'leaf': 'closed_no_order'},
                {
                    'id': 'closed_with_order',
                    'label': 'با شماره سفارش',
                    'children': (
                        {'id': 'closed_with_order_stopped', 'leaf': 'closed_with_order_stopped'},
                        {'id': 'closed_with_order_done', 'leaf': 'closed_with_order_done'},
                        {'id': 'closed_with_order_payment', 'leaf': 'closed_with_order_payment'},
                        {'id': 'closed_with_order_other', 'leaf': 'closed_with_order_other'},
                    ),
                },
            ),
        },
        {
            'id': 'open',
            'label': 'باز / در جریان',
            'children': (
                {'id': 'open_has_order', 'leaf': 'open_has_order'},
                {'id': 'open_has_order_cmd_no_order', 'leaf': 'open_has_order_cmd_no_order'},
                {'id': 'open_has_preinvoice_no_cmd', 'leaf': 'open_has_preinvoice_no_cmd'},
                {'id': 'open_has_inquiry_no_preinvoice', 'leaf': 'open_has_inquiry_no_preinvoice'},
                {'id': 'open_no_inquiry', 'leaf': 'open_no_inquiry'},
            ),
        },
    )

    ITER_FIELDS = (
        'pk', 'purchase_number', 'line_number', 'product_title', 'status',
        'current_status', 'inquiry_number', 'preinvoice_number',
        'order_number', 'order_request_number', 'order_request_status',
        'payment_request_number', 'payment_request_amount',
        'payment_completion_date', 'payment_registration_date',
        'delivery_number', 'delivery_date', 'delivered_quantity',
    )

    @classmethod
    def _is_closed_status(cls, status: str) -> bool:
        return 'بسته' in (status or '').strip()

    @classmethod
    def classify_leaf(cls, purchase) -> str:
        is_closed = cls._is_closed_status(getattr(purchase, 'status', ''))
        has_inquiry = is_valid_value(purchase.inquiry_number)
        has_preinvoice = is_valid_value(purchase.preinvoice_number)
        has_order_cmd = is_valid_value(purchase.order_number)
        has_order_req = is_valid_value(purchase.order_request_number)

        if is_closed:
            if not has_order_req:
                return 'closed_no_order'
            if purchase.current_status == Purchase.CurrentStatus.ORDER_STOPPED or purchase.is_order_stopped:
                return 'closed_with_order_stopped'
            if purchase.current_status in (
                Purchase.CurrentStatus.PAID,
                Purchase.CurrentStatus.DELIVERED,
            ):
                return 'closed_with_order_done'
            if purchase.current_status == Purchase.CurrentStatus.WAITING_PAYMENT:
                return 'closed_with_order_payment'
            return 'closed_with_order_other'

        if has_order_req:
            return 'open_has_order'
        if has_order_cmd:
            return 'open_has_order_cmd_no_order'
        if has_preinvoice:
            return 'open_has_preinvoice_no_cmd'
        if has_inquiry:
            return 'open_has_inquiry_no_preinvoice'
        return 'open_no_inquiry'

    @classmethod
    def _count_leaves(cls, queryset) -> Dict[str, int]:
        counts = {leaf_id: 0 for leaf_id in cls.LEAF_META}
        for row in queryset.values('pk', *cls.ITER_FIELDS[1:]).iterator(chunk_size=1000):
            purchase = Purchase(**row)
            leaf_id = cls.classify_leaf(purchase)
            counts[leaf_id] += 1
        return counts

    @classmethod
    def _node_label(cls, node: Mapping) -> str:
        if 'leaf' in node:
            return cls.LEAF_META[node['leaf']]['label']
        return node.get('label') or cls.LEAF_META.get(node.get('leaf', ''), {}).get('label', node['id'])

    @classmethod
    def _build_branch(cls, node: Mapping, counts: Dict[str, int]) -> Dict[str, Any]:
        if 'leaf' in node:
            leaf_id = node['leaf']
            value = counts.get(leaf_id, 0)
            return {
                'id': leaf_id,
                'label': cls.LEAF_META[leaf_id]['label'],
                'value': value,
                'is_leaf': True,
            }

        children = [
            cls._build_branch(child, counts)
            for child in node.get('children', ())
        ]
        value = sum(child['value'] for child in children)
        return {
            'id': node['id'],
            'label': cls._node_label(node),
            'value': value,
            'children': [child for child in children if child['value'] > 0],
            'is_leaf': False,
        }

    @classmethod
    def build_tree(cls, queryset) -> Dict[str, Any]:
        counts = cls._count_leaves(queryset)
        total = sum(counts.values())
        children = [
            cls._build_branch(branch, counts)
            for branch in cls.TREE_BRANCHES
        ]
        children = [child for child in children if child['value'] > 0]

        return {
            'total': total,
            'tree': {
                'id': cls.ROOT_ID,
                'label': 'همه درخواست‌های خرید',
                'value': total,
                'children': children,
                'is_leaf': False,
            },
            'counts': counts,
        }

    @classmethod
    def _graph_node_name(cls, label: str, value: int) -> str:
        return f'{label}\n{value:,}'.replace(',', '٬')

    @classmethod
    def _layout_graph(
        cls,
        node: Mapping,
        depth: int,
        row_counter: List[int],
        nodes: List[Dict[str, Any]],
        links: List[Dict[str, Any]],
        parent_id: Optional[str] = None,
    ) -> float:
        node_id = node['id']
        children = node.get('children') or []

        if children:
            child_positions = [
                cls._layout_graph(child, depth + 1, row_counter, nodes, links, node_id)
                for child in children
            ]
            y = sum(child_positions) / len(child_positions)
        else:
            y = float(row_counter[0])
            row_counter[0] += 1

        value = int(node.get('value') or 0)
        label = node.get('label') or node_id
        nodes.append({
            'id': node_id,
            'name': cls._graph_node_name(label, value),
            'label': label,
            'value': value,
            'depth': depth,
            'x': depth,
            'y': y,
            'symbolSize': max(28, min(52, 24 + int(value ** 0.5))),
        })
        if parent_id:
            links.append({
                'source': parent_id,
                'target': node_id,
                'value': value,
            })
        return y

    DEPTH_GAP = 220
    ROW_GAP = 118
    GRAPH_PADDING_X = 60
    GRAPH_PADDING_Y = 56
    LABEL_EXTENT_BELOW = 48

    NODE_COLORS = {
        0: '#4f46e5',
        1: '#0ea5e9',
        2: '#10b981',
    }
    NODE_COLOR_DEFAULT = '#f59e0b'

    @classmethod
    def _node_color(cls, depth: int) -> str:
        return cls.NODE_COLORS.get(depth, cls.NODE_COLOR_DEFAULT)

    @classmethod
    def _apply_graph_layout(
        cls,
        nodes: List[Dict[str, Any]],
        links: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        if not nodes:
            return {'width': 800, 'height': 400}

        max_depth = max(node['depth'] for node in nodes)
        max_row = max(node['y'] for node in nodes)
        node_by_id = {}

        for node in nodes:
            node['px'] = (max_depth - node['depth']) * cls.DEPTH_GAP + cls.GRAPH_PADDING_X
            node['py'] = node['y'] * cls.ROW_GAP + cls.GRAPH_PADDING_Y
            node['color'] = cls._node_color(node['depth'])
            node['radius'] = max(14, min(26, int(node.get('symbolSize', 28)) // 2))
            node['label_y'] = node['radius'] + 16
            node['value_y'] = node['radius'] + 32
            node_by_id[node['id']] = node

        for link in links:
            source = node_by_id[link['source']]
            target = node_by_id[link['target']]
            link['x1'] = source['px']
            link['y1'] = source['py']
            link['x2'] = target['px']
            link['y2'] = target['py']
            link['stroke_width'] = round(
                max(1.5, min(4.0, math.log((link.get('value') or 0) + 2))),
                1,
            )

        bottom_extent = cls.GRAPH_PADDING_Y + cls.LABEL_EXTENT_BELOW
        return {
            'width': (max_depth + 1) * cls.DEPTH_GAP + cls.GRAPH_PADDING_X * 2,
            'height': int(max_row * cls.ROW_GAP + cls.GRAPH_PADDING_Y + bottom_extent),
        }

    @classmethod
    def build_graph(cls, queryset) -> Dict[str, Any]:
        """گراف جهت‌دار وضعیت خرید — گره‌ها و یال‌ها بر اساس ستون‌های خرید."""
        summary = cls.build_tree(queryset)
        nodes: List[Dict[str, Any]] = []
        links: List[Dict[str, Any]] = []
        cls._layout_graph(summary['tree'], 0, [0], nodes, links)
        layout = cls._apply_graph_layout(nodes, links)
        return {
            'total': summary['total'],
            'nodes': nodes,
            'links': links,
            'width': layout['width'],
            'height': max(layout['height'], 480),
        }

    @classmethod
    def _find_branch_definition(
        cls,
        node_id: str,
        branches: Optional[tuple] = None,
    ) -> Optional[Mapping]:
        for branch in branches or cls.TREE_BRANCHES:
            if branch.get('id') == node_id:
                return branch
            children = branch.get('children')
            if children:
                found = cls._find_branch_definition(node_id, children)
                if found:
                    return found
        return None

    @classmethod
    def _collect_leaf_ids(cls, node: Mapping) -> List[str]:
        if 'leaf' in node:
            return [node['leaf']]
        leaf_ids: List[str] = []
        for child in node.get('children', ()):
            leaf_ids.extend(cls._collect_leaf_ids(child))
        return leaf_ids

    @classmethod
    def get_node_leaf_ids(cls, node_id: str) -> List[str]:
        if node_id == cls.ROOT_ID:
            return list(cls.LEAF_META.keys())
        if node_id in cls.LEAF_META:
            return [node_id]
        branch = cls._find_branch_definition(node_id)
        if not branch:
            return []
        return cls._collect_leaf_ids(branch)

    @classmethod
    def get_node_meta(cls, node_id: str) -> Optional[Dict[str, str]]:
        if node_id == cls.ROOT_ID:
            return {'id': cls.ROOT_ID, 'label': 'همه درخواست‌های خرید'}
        if node_id in cls.LEAF_META:
            return {'id': node_id, 'label': cls.LEAF_META[node_id]['label']}
        branch = cls._find_branch_definition(node_id)
        if branch:
            return {
                'id': node_id,
                'label': branch.get('label') or cls._node_label(branch),
            }
        return None

    @classmethod
    def _purchase_row_dict(cls, row: Mapping) -> Dict[str, Any]:
        return {
            'pk': row['pk'],
            'purchase_number': row['purchase_number'],
            'line_number': row['line_number'],
            'product_title': (row.get('product_title') or '')[:60],
            'status': row.get('status') or '—',
            'current_status': Purchase.get_status_label(row.get('current_status') or ''),
            'order_request_number': row.get('order_request_number') or '—',
            'order_number': row.get('order_number') or '—',
            'preinvoice_number': row.get('preinvoice_number') or '—',
            'inquiry_number': row.get('inquiry_number') or '—',
        }

    @classmethod
    def get_node_purchases_page(
        cls,
        queryset,
        node_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[List[Dict[str, Any]], int]:
        leaf_ids = cls.get_node_leaf_ids(node_id)
        if not leaf_ids:
            return [], 0

        leaf_set = set(leaf_ids)
        rows: List[Dict[str, Any]] = []
        matched = 0
        safe_offset = max(offset, 0)
        safe_limit = max(limit, 1)

        for row in queryset.values(*cls.ITER_FIELDS).iterator(chunk_size=500):
            purchase = Purchase(**{k: row[k] for k in row if k != 'pk'})
            purchase.pk = row['pk']
            if cls.classify_leaf(purchase) not in leaf_set:
                continue
            if matched >= safe_offset and len(rows) < safe_limit:
                rows.append(cls._purchase_row_dict(row))
            matched += 1

        return rows, matched

    @classmethod
    def get_node_purchases(
        cls,
        queryset,
        node_id: str,
        limit: Optional[int] = 200,
    ) -> List[Dict[str, Any]]:
        rows, _ = cls.get_node_purchases_page(
            queryset,
            node_id,
            offset=0,
            limit=limit if limit is not None else 10_000_000,
        )
        return rows

    @classmethod
    def get_leaf_purchases(cls, queryset, leaf_id: str, limit: Optional[int] = 200) -> List[Dict[str, Any]]:
        return cls.get_node_purchases(queryset, leaf_id, limit=limit)