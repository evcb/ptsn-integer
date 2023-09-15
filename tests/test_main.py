import pytest
from main import main


class TestMain:

    def test_main_csqf(self, csqf_main_args):
        with pytest.raises(SystemExit) as e:
            main(csqf_main_args)

        assert e.type == SystemExit

    def test_main_mcqf(self, mcqf_main_args):
        with pytest.raises(SystemExit) as e:
            main(mcqf_main_args)

        assert e.type == SystemExit