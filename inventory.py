#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.model import Workflow, Model, ModelView, ModelSQL, fields
from trytond.pyson import Not, Equal, Eval, Or, Bool
from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Inventory', 'InventoryLine']
__metaclass__ = PoolMeta


class Inventory:
    __name__ = 'stock.inventory'
    product_category = fields.Many2One('product.category', 'Category')
    init_quantity = fields.Boolean('Init Quanity')


    @classmethod
    @ModelView.button
    def complete_lines(cls, inventories):
        '''
        Complete or update the inventories
        '''
        pool = Pool()
        Line = pool.get('stock.inventory.line')
        Product = pool.get('product.product')

        grouping = cls.grouping()
        to_create = []
        for inventory in inventories:
            # Compute product quantities


            Category = pool.get('product.category')
            search = []
            product_ids =[]
            if inventory.product_category:
                search = [('parent', 'child_of', [inventory.product_category.id])]
                categories = Category.search(search)
                products = Product.search([('category', 'in', categories)])
                product_ids = [p.id for p in products]

            with Transaction().set_context(stock_date_end=inventory.date):
                pbl = Product.products_by_location(
                    [inventory.location.id], grouping=grouping)

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

            # Create lines if needed
            for key, quantity in pbl.iteritems():
                product_id = key[grouping.index('product') + 1]

                if inventory.product_category and product_id not in product_ids:
                    continue

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


class InventoryLine:
    __name__ = 'stock.inventory.line'

    @classmethod
    def create_values4complete(cls, inventory, quantity):
        values = super(InventoryLine, cls).create_values4complete(inventory,
            quantity)
    
        if inventory.init_quantity:
            values['quantity'] = 0.0
        
        return values
