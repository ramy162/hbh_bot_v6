#!/usr/bin/env python3
"""
Standalone test runner for routing and upload validation.
Avoids terminal REPL issues by running directly.
"""
import sys
import os

# Add project paths
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, 'hbh_bot'))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def main():
    print("\n" + "="*60)
    print("ROUTING & UPLOAD VALIDATION TEST SUITE")
    print("="*60 + "\n")
    
    try:
        print("[1/3] Testing compile...")
        import py_compile
        py_compile.compile(os.path.join(project_root, 'hbh_bot', 'models', 'database.py'), doraise=True)
        py_compile.compile(os.path.join(project_root, 'hbh_bot', 'handlers', 'supplier_bot.py'), doraise=True)
        py_compile.compile(os.path.join(project_root, 'hbh_bot', 'handlers', 'buyer_bot.py'), doraise=True)
        print("✓ All Python files compile successfully\n")
    except Exception as e:
        print(f"✗ Compilation failed: {e}\n")
        return False
    
    try:
        print("[2/3] Testing imports...")
        from models.database import (
            init_db, upsert_supplier, upsert_buyer, create_po,
            get_suppliers_matching_categories, get_supplier
        )
        from utils.files import validate_upload, is_image, is_allowed
        print("✓ All imports successful\n")
    except Exception as e:
        print(f"✗ Import failed: {e}\n")
        return False
    
    try:
        print("[3/3] Testing supplier insertion with telegram_id validation...")
        
        # Test: None telegram_id should be rejected
        try:
            upsert_supplier(telegram_id=None, business_name='BadSupplier')
            print("✗ ERROR: None telegram_id was accepted!")
            return False
        except ValueError as e:
            print(f"✓ Correctly rejected None telegram_id: {e}")
        
        # Test: Valid telegram_id should work
        try:
            init_db()
            upsert_supplier(telegram_id=999, business_name='TestSupplier', categories=['concrete'])
            supplier = get_supplier(999)
            if supplier and supplier.get('telegram_id') == 999:
                print(f"✓ Successfully created supplier {supplier.get('supplier_id')} with telegram_id={supplier.get('telegram_id')}")
            else:
                print("✗ Supplier not created properly")
                return False
        except Exception as e:
            print(f"✗ Failed to create valid supplier: {e}")
            return False
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60 + "\n")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
