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
            },
        depends=['state'])
    init_quantity_zero = fields.Boolean('Init Quanity Zero', states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'],
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
        to_create = []
        for inventory in inventories:
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

            with Transaction().set_context(stock_date_end=inventory.date):
                pbl = Product.products_by_location(
                    [inventory.location.id], grouping_filter=(product_ids,),
                    grouping=grouping)

            # Index some data
            product2type = {}
            product2consumable = {}
            for product in Product.browse([line[1] for line in pbl]):
                product2type[product.id] = product.type
                product2consumable[product.id] = product.consumable

            # Update existing lines
            for line in inventory.lines:
                if not (line.product.active and
                        line.product.type == 'goods'
                        and not line.product.consumable):
                    Line.delete([line])
                    continue

                if inventory.product_category and line.product not in products:
                    Line.delete([line])
                    continue

                key = (inventory.location.id,) + line.unique_key
                if key in pbl:
                    quantity = pbl.pop(key)
                else:
                    quantity = 0.0
                values = line.update_values4complete(quantity)
                if values:
                    Line.write([line], values)

            if not fill:
                continue

            # Create lines if needed
            for key, quantity in pbl.items():
                product_id = key[grouping.index('product') + 1]

                if (product2type[product_id] != 'goods'
                        or product2consumable[product_id]):
                    continue
                if not quantity:
                    continue

                values = Line.create_values4complete(inventory, quantity)
                for i, fname in enumerate(grouping, 1):
                    values[fname] = key[i]
                to_create.append(values)
        if to_create:
            Line.create(to_create)


class InventoryLine(metaclass=PoolMeta):
    __name__ = 'stock.inventory.line'

    @classmethod
    def create_values4complete(cls, inventory, quantity):
        values = super(InventoryLine, cls).create_values4complete(inventory,
            quantity)
        if inventory.init_quantity_zero:
            values['quantity'] = 0.0
        return values
