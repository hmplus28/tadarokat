"""جستجوی یکپارچه — شماره خرید، شماره سفارش و سایر فیلدهای پرونده"""
from __future__ import annotations

from django.db.models import Q, QuerySet


class SearchService:
    PURCHASE_FIELDS = (
        'purchase_number',
        'order_request_number',
        'order_number',
        'inquiry_number',
        'product_title',
        'product_code',
        'expert_name',
        'requester',
        'product_category',
        'base_number',
        'supplier',
    )

    ORDER_FIELDS = (
        'order_number',
        'product_title',
        'contractor',
        'expert_name',
    )

    ORDER_PURCHASE_FIELDS = (
        'purchase__purchase_number',
        'purchase__order_request_number',
        'purchase__product_title',
        'purchase__product_code',
    )

    INQUIRY_FIELDS = (
        'inquiry_number',
        'purchase__purchase_number',
        'purchase__order_request_number',
        'purchase__product_title',
        'purchase__product_code',
        'purchase__expert_name',
    )

    DELIVERY_FIELDS = (
        'delivery_number',
        'product_title',
        'receiver',
        'order__order_number',
        'purchase__purchase_number',
        'purchase__order_request_number',
    )

    @classmethod
    def _build_q(cls, search: str, fields: tuple[str, ...]) -> Q | None:
        term = (search or '').strip()
        if not term:
            return None
        query = Q()
        for field in fields:
            query |= Q(**{f'{field}__icontains': term})
        return query

    @classmethod
    def filter_purchases(cls, queryset: QuerySet, search: str) -> QuerySet:
        query = cls._build_q(search, cls.PURCHASE_FIELDS)
        return queryset.filter(query) if query is not None else queryset

    @classmethod
    def filter_orders(cls, queryset: QuerySet, search: str) -> QuerySet:
        query = cls._build_q(search, cls.ORDER_FIELDS)
        purchase_query = cls._build_q(search, cls.ORDER_PURCHASE_FIELDS)
        if query is None and purchase_query is None:
            return queryset
        combined = Q()
        if query is not None:
            combined |= query
        if purchase_query is not None:
            combined |= purchase_query
        return queryset.filter(combined)

    @classmethod
    def filter_inquiries(cls, queryset: QuerySet, search: str) -> QuerySet:
        query = cls._build_q(search, cls.INQUIRY_FIELDS)
        return queryset.filter(query) if query is not None else queryset

    @classmethod
    def filter_deliveries(cls, queryset: QuerySet, search: str) -> QuerySet:
        query = cls._build_q(search, cls.DELIVERY_FIELDS)
        return queryset.filter(query) if query is not None else queryset