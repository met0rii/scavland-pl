"""Compatibility entry point for the portable release builder."""
import sys
from release import main
if __name__ == '__main__':
    sys.argv.insert(1, 'build')
    main()
