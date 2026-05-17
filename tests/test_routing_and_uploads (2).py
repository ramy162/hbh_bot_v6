"""
Simple integration-style tests for supplier routing and upload validation.
Run with: python -m tests.test_routing_and_uploads or python tests/test_routing_and_uploads.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hbh_bot'))

from models.database import (
    init_db, upsert_supplier, upsert_buyer, create_po,
    get_suppliers_matching_categories, get_supplier
)
from utils.files import validate_upload, is_image, is_allowed

# Minimal fake objects to simulate telegram.Message
class FakeDocument:
    def __init__(self, file_id, file_name):
        self.file_id = file_id
        self.file_name = file_name

class FakePhotoSize:
    def __init__(self, file_id):
        self.file_id = file_id

class FakeMessage:
    def __init__(self, document=None, photo=None):
        self.document = document
        self.photo = photo


def run_tests():
    print('Initializing DB...')
    init_db()

    # Clean slate: create two suppliers
    print('Creating suppliers...')
    upsert_supplier(telegram_id=11111, business_name='ConcreteCo', phone='091100000', categories=['concrete', 'steel'])
    # Only create suppliers with valid telegram_id (NOT NULL constraint)
    upsert_supplier(telegram_id=22222, business_name='WoodWorks', phone='091122222', categories=['wood'])

    # Create buyer
    upsert_buyer(telegram_id=22222, name='TestBuyer')

    # Create PO with mixed-case category to test normalization
    po = create_po(1, categories=['Concrete'], material_detail='45 bags cement')
    print('Created PO:', po.get('po_code'), 'categories stored:', po.get('categories'))

    # Test supplier matching
    matches = get_suppliers_matching_categories(['Concrete'])
    print('Matches returned:', len(matches))
    for m in matches:
        print(' - Supplier:', m.get('supplier_id'), 'tg:', m.get('telegram_id'), 'cats:', m.get('categories'))

    # Validate behavior: ensure supplier with telegram_id present
    assert any(m.get('telegram_id') for m in matches), 'No suppliers with telegram_id matched!'

    # Test validate_upload with fake doc
    print('\nTesting validate_upload...')
    msg_ok = FakeMessage(document=FakeDocument('FILE123', 'specs.pdf'))
    ok, err = validate_upload(msg_ok)
    print('PDF test -> valid:', ok, 'err:', err)
    assert ok

    msg_bad = FakeMessage(document=FakeDocument('FILE124', 'malware.exe'))
    ok2, err2 = validate_upload(msg_bad)
    print('EXE test -> valid:', ok2, 'err:', err2)
    assert not ok2

    # Test image detection
    print('\nTesting is_image/is_allowed...')
    print('is_image(test.jpg):', is_image('test.jpg'))
    print('is_allowed(test.jpg):', is_allowed('test.jpg'))
    print('is_allowed(unknown.ext):', is_allowed('unknown.ext'))

    print('\nAll tests completed successfully.')

if __name__ == '__main__':
    run_tests()
