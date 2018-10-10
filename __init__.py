# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import inventory

def register():
    Pool.register(
        inventory.Inventory, 
        inventory.InventoryLine,
        module='stock_inventory_product_category', type_='model')
