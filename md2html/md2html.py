import getopt, sys
from . import cli

def main():
    argumentList = sys.argv[1:]
    options = "hmo:"
    long_options = ["help", "my_file", "output="]
    try:
        cfg = cli.parse_args(argumentList)
        print(f"cfg is {cfg['output']}")
    except getopt.error as err:
        print (str(err))

if __name__ == "__main__":
    main()
