def prepare_msg(tmplt, msg):
    if not tmplt.strip():
        return msg
    new_str = tmplt.replace("{message}", msg)
    return new_str
