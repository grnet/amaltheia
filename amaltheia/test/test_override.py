from amaltheia.utils import override


class TestOverride:

    def test_simple(self):
        x = {'a': 'b'}
        override(x, 'a', 'c')
        assert x == {'a': 'c'}

    def test_dict(self):
        x = {'a': {'b': 'c'}}
        override(x, 'a.b', 'd')
        assert x == {'a': {'b': 'd'}}

    def test_list(self):
        x = {'a': {'b': ['c', {'d': 'e'}]}}
        override(x, 'a.b[1].d', 'f')
        assert x == {'a': {'b': ['c', {'d': 'f'}]}}

    def test_list_in_list(self):
        x = [['a']]
        override(x, '[0][0]', 'b')
        assert x == [['b']]

    def test_list_out_of_bounds(self):
        x = [['a']]
        override(x, '[0][2]', 'b')
        assert x == [['a']]

    def test_dict_key(self):
        x = {'a': 'b'}
        override(x, '[a]', 'c')
        assert x == {'a': 'c'}
