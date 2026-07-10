"""همگام‌سازی گروه‌های کالایی از داده اکسل و پرونده‌ها"""
from __future__ import annotations

from typing import Iterable, Set

from accounts.models import ProductCategory


class ProductCategoryService:
    @classmethod
    def _normalize_names(cls, names: Iterable[str]) -> Set[str]:
        return {
            name.strip()
            for name in names
            if name and str(name).strip()
        }

    @classmethod
    def ensure_categories(cls, names: Iterable[str]) -> int:
        """گروه جدید بسازد؛ گروه موجود را دست نمی‌زند."""
        normalized = cls._normalize_names(names)
        if not normalized:
            return 0

        created = 0
        base_order = ProductCategory.objects.count()
        for index, name in enumerate(sorted(normalized), start=1):
            _, was_created = ProductCategory.objects.get_or_create(
                name=name,
                defaults={
                    'sort_order': base_order + index,
                    'is_active': True,
                },
            )
            if was_created:
                created += 1
        return created

    @classmethod
    def sync_from_purchases(cls) -> int:
        from purchases.models import Purchase

        names = (
            Purchase.objects
            .exclude(product_category='')
            .values_list('product_category', flat=True)
            .distinct()
        )
        return cls.ensure_categories(names)