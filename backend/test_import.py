import traceback
try:
    import main
    print('SUCCESS')
except Exception as e:
    print('ERROR OCCURRED:')
    traceback.print_exc()
