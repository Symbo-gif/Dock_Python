from d2p.PARSERS.env_parser import EnvParser

def test_parse_from_string():
    content = """
    KEY1=VALUE1
    KEY2 = VALUE2
    # This is a comment
    KEY3="VALUE3" # Trailing comment
    KEY4='VALUE4'
    """
    env = EnvParser.parse_from_string(content)
    assert env['KEY1'] == 'VALUE1'
    assert env['KEY2'] == 'VALUE2'
    assert env['KEY3'] == 'VALUE3'
    assert env['KEY4'] == 'VALUE4'
    assert 'KEY5' not in env
