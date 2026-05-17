import runpy, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hbh_bot'))
runpy.run_path('tests/test_routing_and_uploads.py', run_name='__main__')
