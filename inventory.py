# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

__all__ = ['Inventory', 'InventoryLine']


class Inventory(metaclass=PoolMeta):
    __name__ = 'stock.inventory'

    product_category = fields.Many2One('product.category', 'Category', states={
            'readonly': Eval('state') != 'draft',
            })
    init_quantity_zero = fields.Boolean('Init Quanity Zero', states={
            'readonly': Eval('state') != 'draft',
            },
        help='Mark this option to init the quantity of new lines created by '
        '"Complete Inventory" to zero.')

    @classmethod
    @ModelView.button
    def complete_lines(cls, inventories, fill=True):
        '''
        Complete or update the inventories
        '''
        pool = Pool()
        Category = pool.get('product.category')
        Line = pool.get('stock.inventory.line')
        Product = pool.get('product.product')

        grouping = cls.grouping()
        to_save, to_delete = [], []
        for inventory in inventories:
            # Once done computation is wrong because include created moves
            if inventory.state == 'done':
                continue

            # Compute product quantities
            product_ids = None
            if inventory.product_category:
                categories = Category.search([
                        ('parent', 'child_of',
                            [inventory.product_category.id]),
                        ])
                products = Product.search([('categories.id', 'in', [x.id
                    for x in categories])])
                product_ids = [p.id for p in products]

            # Compute product quantities
            with Transaction().set_context(
                    company=inventory.company.id,
                    stock_date_end=inventory.date):
                pbl = Product.products_by_location(
                    [inventory.location.id], grouping_filter=(product_ids,),
                    grouping=grouping)

            # Update existing lines
            for line in inventory.lines:
                if line.product.type != 'goods':
                    to_delete.append(line)
                    continue

                key = (inventory.location.id,) + line.unique_key
                if key in pbl:
                    quantity = pbl.pop(key)
                else:
                    quantity = 0.0
                line.update_for_complete(quantity)
                to_save.append(line)

            if not fill:
                continue

            product_idx = grouping.index('product') + 1
            # Index some data
            product2type = {}
            product2consumable = {}
            for product in Product.browse({line[product_idx] for line in pbl}):
                product2type[product.id] = product.type
                product2consumable[product.id] = product.consumable

            # Create lines if needed
            for key, quantity in pbl.items():
                product_id = key[product_idx]
                if (product2type[product_id] != 'goods'
                        or product2consumable[product_id]):
                    continue
                if not quantity:
                    continue

                line = Line(
                    inventory=inventory,
                    **{fname: key[i] for i, fname in enumerate(grouping, 1)})
                line.update_for_complete(quantity)
                to_save.append(line)
        if to_delete:
            Line.delete(to_delete)
        if to_save:
            Line.save(to_save)


class InventoryLine(metaclass=PoolMeta):
    __name__ = 'stock.inventory.line'

    @fields.depends('inventory')
    def update_for_complete(self, quantity):
        super().update_for_complete(quantity)
        if self.inventory and self.inventory.init_quantity_zero:
            self.quantity = 0.0
