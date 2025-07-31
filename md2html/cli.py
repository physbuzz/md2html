import getopt, sys

def parse_args(argv):
    options = "hmo:"
    long_options = ["help", "my_file", "output="]
    args, _ = getopt.getopt(argv, options, long_options)

    config = {"help": False, "my_file": False, "output": None}
    for opt, val in args:
        if opt in ("-h", "--help"):
            config["help"] = True
        elif opt in ("-m", "--my_file"):
            config["my_file"] = True
        elif opt in ("-o", "--output"):
            config["output"] = val
    return config
