import sys
print('Test script running')
try:
    import jwt
    print('jwt is installed')
except ImportError:
    print('jwt is NOT installed')

