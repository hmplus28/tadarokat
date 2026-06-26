from typing import Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from auth.dependencies import get_current_user, require_roles, require_write_access
from config import MANAGER_ROLES
from services import expert_service
from services import access_service, admin_service, analytics_service, delivery_service, excel_service, history_service, inquiry_service, notification_service, order_service, workflow_import_service

router = APIRouter(prefix="/api", tags=["data"])


def _expert_filter(user: dict, expert: Optional[str]) -> Optional[str]:
    if user["role"] == "expert":
        return user.get("expert")
    return expert


def _is_manager(user: dict) -> bool:
    return user.get("role") in MANAGER_ROLES


@router.get("/health")
def health():
    from db.connection import is_system_locked
    from services.bootstrap_service import get_setup_status

    setup = get_setup_status()
    return {
        "status": "ok" if setup.get("login_ok") else "setup_required",
        "ready": setup.get("ready"),
        "locked": is_system_locked(),
        "setup": setup,
        "data": excel_service.excel_info(),
    }


@router.get("/system/setup")
def system_setup():
    from services.bootstrap_service import get_setup_status
    return get_setup_status()


@router.get("/system/paths")
def system_paths(user: dict = Depends(require_roles("admin"))):
    from services import settings_service
    return settings_service.get_paths_overview()


@router.get("/system/paths/defaults")
def system_path_defaults(
    share_dir: str = Query(..., min_length=1),
    user: dict = Depends(require_roles("admin")),
):
    from services import settings_service
    return {"paths": settings_service.default_paths_from_share(share_dir)}


@router.patch("/system/paths")
def update_system_paths(payload: dict, user: dict = Depends(require_roles("admin"))):
    from services import settings_service
    try:
        return {"ok": True, "paths": settings_service.save_settings(payload, user["username"])}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/system/database")
def system_database(user: dict = Depends(get_current_user)):
    from db.connection import get_db_manager, is_system_locked
    return {
        "locked": is_system_locked(),
        "database": get_db_manager().db_info(),
        "storage": excel_service.excel_info(),
    }


@router.post("/system/export-excel")
def system_export_excel(user: dict = Depends(require_roles("admin", "manager"))):
    from db.export_service import export_to_excel
    try:
        path = export_to_excel()
        return {"ok": True, "path": str(path)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/system/import-schedule")
def get_import_schedule(user: dict = Depends(require_roles("admin"))):
    from services.import_scheduler_service import get_schedule
    return get_schedule()


@router.patch("/system/import-schedule")
def update_import_schedule(payload: dict, user: dict = Depends(require_roles("admin"))):
    from services.import_scheduler_service import save_schedule
    try:
        return save_schedule(
            enabled=payload.get("enabled"),
            hour=payload.get("hour"),
            minute=payload.get("minute"),
            set_this_machine_runner=bool(payload.get("set_this_machine_runner")),
            username=user.get("username") or "admin",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/system/import-schedule/run-now")
def run_import_schedule_now(user: dict = Depends(require_roles("admin"))):
    from services.import_scheduler_service import run_import_job
    try:
        return run_import_job(triggered_by=f"manual:{user.get('username')}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/system/import-excel")
def system_import_excel(
    user: dict = Depends(require_roles("admin")),
    input_path: str = Query(default=""),
):
    """اجرای دستی import — admin."""
    from services.import_scheduler_service import run_import_job
    try:
        if input_path:
            from db.import_service import run_import
            return run_import(input_path)
        return run_import_job(triggered_by=f"manual:{user.get('username')}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/data/refresh")
def refresh_data_from_db(user: dict = Depends(get_current_user)):
    """بروزرسانی cache — دریافت آخرین داده از پایگاه share (همه نقش‌ها)."""
    from datetime import datetime

    from db.connection import get_db_manager, is_system_locked

    if is_system_locked():
        raise HTTPException(
            status_code=409,
            detail="import در حال انجام است — چند ثانیه بعد دوباره «آخرین داده» را بزنید",
        )
    excel_service.invalidate_cache()
    excel_service.warm_cache()
    db_info = {}
    try:
        db_info = get_db_manager().db_info()
    except Exception:
        pass
    return {
        "ok": True,
        "message": "آخرین داده از پایگاه دریافت شد",
        "database": db_info,
        "refreshed_at": datetime.utcnow().isoformat(),
    }


@router.get("/stats")
def stats(user: dict = Depends(get_current_user), expert: Optional[str] = Query(default=None)):
    return excel_service.get_purchase_stats(expert=_expert_filter(user, expert))


@router.get("/requests")
def requests(
    user: dict = Depends(get_current_user),
    search: str = Query(default=""),
    filter: str = Query(default=""),
    expert: Optional[str] = Query(default=None),
    urgency: str = Query(default=""),
    purchase_type: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
):
    return excel_service.get_purchase_requests(
        search=search,
        filter_type=filter,
        expert=_expert_filter(user, expert),
        urgency=urgency,
        purchase_type=purchase_type,
        page=page,
        page_size=page_size,
    )


@router.get("/requests/detail/{request_number}")
def request_detail(request_number: str, user: dict = Depends(get_current_user)):
    row = excel_service.get_purchase_request_detail(request_number)
    if not row:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    if user["role"] == "expert" and user.get("expert"):
        expert_val = str(row.get("کارشناس خرید", ""))
        if user["expert"] not in expert_val:
            raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")
    return row


@router.patch("/requests/{request_number}")
def update_request(request_number: str, payload: dict, user: dict = Depends(require_roles("admin"))):
    try:
        return excel_service.update_purchase_request(
            request_number, payload, user["username"], admin=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/entities/{entity_type}/{entity_id}")
def admin_get_entity(entity_type: str, entity_id: str, _: dict = Depends(require_roles("admin"))):
    data = admin_service.get_entity(entity_type, entity_id)
    if not data:
        raise HTTPException(status_code=404, detail="رکورد یافت نشد")
    return data


@router.patch("/admin/entities/{entity_type}/{entity_id}")
def admin_update_entity(
    entity_type: str,
    entity_id: str,
    payload: dict,
    user: dict = Depends(require_roles("admin")),
):
    try:
        return admin_service.update_entity(entity_type, entity_id, payload, user["username"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/workflow-import/template")
def workflow_import_template(_: dict = Depends(require_roles("admin"))):
    content = workflow_import_service.build_excel_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="workflow-import-template.xlsx"'},
    )


@router.get("/admin/workflow-import/guide")
def workflow_import_guide(_: dict = Depends(require_roles("admin"))):
    content = workflow_import_service.build_word_guide()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="workflow-import-guide.docx"'},
    )


@router.post("/admin/workflow-import")
async def workflow_import_upload(
    file: UploadFile = File(...),
    user: dict = Depends(require_roles("admin")),
):
    if not file.filename or not str(file.filename).lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="فقط فایل اکسل (.xlsx) پذیرفته می‌شود")
    try:
        content = await file.read()
        return workflow_import_service.import_from_excel(content, user["username"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/inquiries")
def inquiries(
    user: dict = Depends(get_current_user),
    search: str = Query(default=""),
    expert: str = Query(default=""),
    status: str = Query(default=""),
    warehouse: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
):
    if user.get("role") == "expert":
        raise HTTPException(
            status_code=403,
            detail="کارشناس از بخش «صدور استعلام» (درخواست‌های بدون استعلام) استفاده کند",
        )
    return inquiry_service.list_local_inquiries(
        search=search, page=page, page_size=page_size, user=user,
        expert=expert, status=status, warehouse=warehouse,
    )


@router.get("/inquiries/next-number")
def next_inquiry_number(user: dict = Depends(get_current_user)):
    return excel_service.preview_next_inquiry_number()


@router.get("/inquiries/last-purchase")
def last_purchase(
    code: str = Query(default=""),
    title: str = Query(default=""),
    exclude: str = Query(default=""),
    user: dict = Depends(get_current_user),
):
    try:
        return excel_service.get_last_purchase_for_product(
            product_code=code, product_title=title, exclude_purchase=exclude
        )
    except Exception:
        return {"found": False, "source": None, "item": None}


@router.get("/cities/search")
def search_cities(q: str = Query(default=""), user: dict = Depends(get_current_user)):
    from services import local_storage
    return {"items": local_storage.search_cities(q)}


@router.get("/inquiries/lookup/{purchase_number}")
def lookup_purchase(purchase_number: str, user: dict = Depends(get_current_user)):
    data = inquiry_service.lookup_purchase(purchase_number)
    if not data:
        raise HTTPException(status_code=404, detail="درخواست خرید یافت نشد")
    if user.get("role") == "expert":
        try:
            inquiry_service._assert_expert_owns_purchase(data, user)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    return data


@router.get("/contractors/search")
def search_contractors(q: str = Query(default=""), user: dict = Depends(get_current_user)):
    from services import local_storage
    return {"items": local_storage.search_contractors(q)}


@router.get("/inquiries/local")
def local_inquiries(
    user: dict = Depends(require_roles(*MANAGER_ROLES)),
    search: str = Query(default=""),
    expert: str = Query(default=""),
    status: str = Query(default=""),
    warehouse: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
):
    return inquiry_service.list_local_inquiries(
        search=search, page=page, page_size=page_size,
        user=None,
        expert=expert, status=status, warehouse=warehouse,
    )


@router.get("/inquiries/mine")
def my_inquiries(
    user: dict = Depends(require_roles("expert", "admin")),
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
):
    return inquiry_service.list_local_inquiries(
        search=search, page=page, page_size=page_size, user=user, exclude_moved_to_orders=True,
    )


@router.get("/inquiries/detail/{inquiry_number}")
def inquiry_detail(inquiry_number: str, user: dict = Depends(get_current_user)):
    data = inquiry_service.get_inquiry_for_user(inquiry_number, user)
    if not data:
        raise HTTPException(status_code=404, detail="استعلام یافت نشد یا دسترسی ندارید")
    return data


@router.get("/inquiries/compare/{inquiry_number}")
def compare_inquiry(inquiry_number: str, user: dict = Depends(require_roles(*MANAGER_ROLES))):
    data = inquiry_service.get_inquiry_detail(inquiry_number)
    if not data:
        raise HTTPException(status_code=404, detail="استعلام یافت نشد")
    return data


@router.post("/inquiries/issue")
def issue_inquiry(payload: dict, user: dict = Depends(require_roles("expert", "admin"))):
    issuer = user.get("name") or user.get("expert") or user["username"]
    try:
        return inquiry_service.create_inquiry_with_preinvoices(payload, issuer, user["username"], user=user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/experts")
def list_experts(user: dict = Depends(get_current_user)):
    return expert_service.list_experts_for_api()


@router.post("/inquiries/{inquiry_number}/approve-lines")
def approve_inquiry_lines(
    inquiry_number: str,
    payload: dict,
    user: dict = Depends(require_roles(*MANAGER_ROLES)),
):
    manager = user.get("name") or user["username"]
    lines = payload.get("lines") or []
    comment = payload.get("comment") or ""
    issue_orders = payload.get("issue_orders", True)
    if isinstance(issue_orders, str):
        issue_orders = issue_orders.lower() not in ("false", "0", "no")
    try:
        return inquiry_service.manager_approve_lines(
            inquiry_number, lines, manager, user["username"], comment=comment, issue_orders=issue_orders
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/inquiries/preinvoice/{preinvoice_id}/{action}")
def review_preinvoice(
    preinvoice_id: str,
    action: str,
    payload: dict = Body(default={}),
    user: dict = Depends(require_roles(*MANAGER_ROLES)),
):
    reviewer = user.get("name") or user["username"]
    body = payload or {}
    comment = body.get("comment") or body.get("کامنت مدیر") or ""
    try:
        return inquiry_service.manager_decision(
            preinvoice_id, action, reviewer, user["username"], comment=comment
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/orders")
def orders(
    user: dict = Depends(get_current_user),
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
):
    return order_service.list_orders(search=search, page=page, page_size=page_size, user=user)


@router.post("/orders")
def create_order(payload: dict, user: dict = Depends(require_roles(*MANAGER_ROLES))):
    manager = user.get("name") or user["username"]
    try:
        return order_service.issue_order(payload, manager, user["username"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/orders/by-number/{order_number}/workflow")
def order_workflow_by_number(order_number: str, user: dict = Depends(get_current_user)):
    try:
        from services import local_storage
        order = local_storage.find_order_by_number(order_number)
        if order:
            access_service.assert_expert_owns_order(order, user)
            access_service.assert_warehouse_owns_order(order, user)
        return order_service.get_order_workflow_by_number(order_number)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/orders/{order_id}/workflow")
def order_workflow(order_id: str, user: dict = Depends(get_current_user)):
    try:
        from services import local_storage
        orders = local_storage.get_orders()
        if not orders.empty:
            m = orders[orders["id"].astype(str) == str(order_id)]
            if not m.empty:
                access_service.assert_expert_owns_order(m.iloc[0].to_dict(), user)
                access_service.assert_warehouse_owns_order(m.iloc[0].to_dict(), user)
        return order_service.get_order_workflow(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/orders/{order_id}")
def patch_order(order_id: str, payload: dict, user: dict = Depends(require_roles("expert", "admin"))):
    try:
        return order_service.advance_order_stage(order_id, payload, user["username"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/deliveries")
def deliveries(
    user: dict = Depends(get_current_user),
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
):
    return delivery_service.list_deliveries(search=search, page=page, page_size=page_size, user=user)


@router.post("/deliveries")
def create_delivery(payload: dict, user: dict = Depends(require_write_access)):
    try:
        return delivery_service.create_delivery(payload, user["username"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/deliveries/{delivery_id}/workflow")
def delivery_workflow(delivery_id: str, user: dict = Depends(get_current_user)):
    try:
        from services import local_storage
        delivery = local_storage.find_delivery_by_id(delivery_id)
        if delivery:
            access_service.assert_expert_owns_delivery(delivery, user)
        return order_service.get_delivery_workflow(delivery_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/deliveries/{delivery_id}")
def patch_delivery(delivery_id: str, payload: dict, user: dict = Depends(require_write_access)):
    try:
        return delivery_service.update_delivery(delivery_id, payload, user["username"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/warehouse/product-lookup")
def warehouse_product_lookup(
    user: dict = Depends(get_current_user),
    code: str = Query(default=""),
    title: str = Query(default=""),
):
    if user.get("role") != "warehouse":
        raise HTTPException(status_code=403, detail="فقط کاربر انبار")
    from services import warehouse_service

    try:
        return warehouse_service.lookup_product(
            user.get("warehouse") or "",
            product_code=code,
            product_title=title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/warehouse/summary")
def warehouse_summary(user: dict = Depends(get_current_user)):
    if user.get("role") != "warehouse":
        raise HTTPException(status_code=403, detail="فقط کاربر انبار")
    from services import warehouse_service

    return warehouse_service.warehouse_status_summary(user.get("warehouse") or "")


@router.get("/warehouse/dashboard")
def warehouse_dashboard(user: dict = Depends(get_current_user)):
    if user.get("role") != "warehouse":
        raise HTTPException(status_code=403, detail="فقط کاربر انبار")
    from services import warehouse_service

    return warehouse_service.get_warehouse_dashboard(user.get("warehouse") or "")


@router.get("/warehouse/purchases")
def warehouse_purchases(
    user: dict = Depends(get_current_user),
    search: str = Query(default=""),
    stage: str = Query(default=""),
    expert: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
):
    if user.get("role") != "warehouse":
        raise HTTPException(status_code=403, detail="فقط کاربر انبار")
    from services import warehouse_service

    return warehouse_service.list_registered_purchases(
        user.get("warehouse") or "",
        search=search,
        stage_filter=stage,
        expert=expert,
        page=page,
        page_size=page_size,
    )


@router.get("/warehouse/purchases/{inquiry_number}/stages")
def warehouse_purchase_stages(inquiry_number: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "warehouse":
        raise HTTPException(status_code=403, detail="فقط کاربر انبار")
    from services import warehouse_service

    try:
        return warehouse_service.get_purchase_stages(user.get("warehouse") or "", inquiry_number)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/notifications")
def notifications(user: dict = Depends(get_current_user), unread: bool = Query(default=False)):
    is_wh = user.get("role") == "warehouse"
    return {
        "items": notification_service.list_for_user(
            user["username"],
            unread_only=unread,
            delivery_only=is_wh,
            warehouse=user.get("warehouse") if is_wh else None,
        )
    }


@router.get("/warehouses")
def warehouses_list(user: dict = Depends(get_current_user)):
    from services.warehouse_resolver import list_known_warehouses

    return {"items": list_known_warehouses()}


@router.patch("/notifications/{notification_id}/read")
def read_notification(notification_id: str, user: dict = Depends(get_current_user)):
    result = notification_service.mark_read(notification_id, user["username"])
    if not result:
        raise HTTPException(status_code=404, detail="اعلان یافت نشد")
    return result


@router.patch("/notifications/read-all")
def read_all_notifications(user: dict = Depends(get_current_user)):
    is_wh = user.get("role") == "warehouse"
    count = notification_service.mark_all_read(
        user["username"],
        warehouse=user.get("warehouse") if is_wh else None,
        delivery_only=is_wh,
    )
    return {"ok": True, "marked": count}


@router.get("/history")
def edit_history(
    user: dict = Depends(require_roles("admin")),
    search: str = Query(default=""),
    entity_type: str = Query(default=""),
    entity_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
):
    return history_service.list_history(
        search=search, entity_type=entity_type, entity_id=entity_id, page=page, page_size=page_size
    )


@router.get("/reports/duration")
def report_duration(
    period: str = Query(default="month"),
    user: dict = Depends(require_roles(*MANAGER_ROLES)),
):
    return analytics_service.get_duration_dashboard(period=period)


@router.get("/reports/purchase")
def report_purchase(
    user: dict = Depends(get_current_user),
    expert: str = Query(default=""),
    urgency: str = Query(default=""),
    purchase_type: str = Query(default=""),
):
    if user.get("role") in ("expert", "warehouse"):
        raise HTTPException(status_code=403, detail="گزارش خرید فقط برای مدیر در دسترس است")
    return excel_service.get_purchase_summary(
        expert=_expert_filter(user, expert or None),
        urgency=urgency,
        purchase_type=purchase_type,
    )


@router.get("/reports/my")
def report_my(user: dict = Depends(get_current_user)):
    access_service.assert_expert(user, detail="گزارش من فقط برای کارشناس است")
    expert = user.get("expert") or user.get("name")
    if not expert:
        raise HTTPException(status_code=400, detail="کارشناس مرتبط با حساب یافت نشد")
    return excel_service.get_expert_report(expert=expert, include_items=False)


@router.get("/reports/expert")
def report_expert(
    user: dict = Depends(require_roles(*MANAGER_ROLES)),
    expert: str = Query(default=""),
):
    return excel_service.get_expert_report(expert=expert or None)


@router.get("/reports/reorder")
def report_reorder(
    user: dict = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
):
    if user.get("role") in ("expert", "warehouse"):
        raise HTTPException(status_code=403, detail="نقطه سفارش فقط برای مدیر در دسترس است")
    return excel_service.get_reorder_report(
        page=page, page_size=page_size, expert=_expert_filter(user, None),
    )


@router.get("/reports/dashboard")
def report_dashboard(
    user: dict = Depends(get_current_user),
    expert: str = Query(default=""),
):
    exp = _expert_filter(user, expert or None)
    if user.get("role") == "expert":
        return excel_service.get_dashboard(expert=exp, expert_portal=True)
    return excel_service.get_dashboard(
        expert=exp or None,
        include_experts=_is_manager(user) and not exp,
    )


@router.get("/export/excel")
def export_excel(
    view: str = Query(..., description="نام نمای جاری"),
    user: dict = Depends(get_current_user),
    search: str = Query(default=""),
    filter: str = Query(default=""),
    expert: str = Query(default=""),
    status: str = Query(default=""),
    warehouse: str = Query(default=""),
    urgency: str = Query(default=""),
    purchase_type: str = Query(default=""),
    period: str = Query(default="month"),
    entity_type: str = Query(default=""),
    entity_id: str = Query(default=""),
):
    from services import view_export_service

    try:
        content, filename = view_export_service.export_view_xlsx(
            view,
            user,
            search=search,
            filter_type=filter,
            expert=expert,
            status=status,
            warehouse=warehouse,
            urgency=urgency,
            purchase_type=purchase_type,
            period=period,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )