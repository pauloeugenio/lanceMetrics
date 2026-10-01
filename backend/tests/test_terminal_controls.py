from backend.app import terminal

def test_stop_web_command_dispatch(monkeypatch):
    import runpy,sys
    from unittest.mock import patch
    import pytest
    with patch('subprocess.run') as run:
        run.return_value.returncode=0
        monkeypatch.setattr(sys,'argv',['lanceMetrics','stop-web'])
        with pytest.raises(SystemExit) as exc:runpy.run_module('backend.app.terminal',run_name='__main__')
        assert exc.value.code==0
        assert run.call_args.args[0][-1].endswith('/stop.sh')

def test_menu_stop_web_uses_existing_script(monkeypatch,capsys):
    choices=iter(['3','0']);calls=[]
    monkeypatch.setattr('builtins.input',lambda _:next(choices))
    monkeypatch.setattr(terminal,'primary_ip',lambda:'127.0.0.1')
    monkeypatch.setattr(terminal,'run_script',lambda name:calls.append(name) or 0)
    terminal.menu()
    assert 'Stop Web Interface / Parar servidor web' in capsys.readouterr().out
    assert calls==['stop.sh']
