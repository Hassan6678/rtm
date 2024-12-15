def dict_with_default(keys, default_value=0, prefix="", postfix=""):
    fix_key = lambda k: prefix + str(k) + postfix
    return dict.fromkeys(map(fix_key, keys), default_value)
