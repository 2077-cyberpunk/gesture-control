from macros import MacroRecorder


def test_record_and_persist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = MacroRecorder()
    assert m.start_recording("m1") is True
    m.record_action("fist", "left_click", (10, 20))
    m.record_action("open_palm", "mouse_move", (30, 40))
    assert m.stop_recording() == "m1"

    assert (tmp_path / "macros.json").exists()
    reloaded = MacroRecorder()
    assert "m1" in reloaded.saved_macros
    assert len(reloaded.saved_macros["m1"]["actions"]) == 2


def test_record_requires_recording_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = MacroRecorder()
    m.record_action("fist", "left_click")
    assert m.current_macro == []


def test_list_macros_sorted_by_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = MacroRecorder()
    for name in ("a", "b", "c"):
        m.start_recording(name)
        m.record_action("fist", "left_click")
        m.stop_recording()
    names = [x["name"] for x in m.list_macros()]
    assert names == ["c", "b", "a"]


def test_rename_and_delete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = MacroRecorder()
    m.start_recording("old")
    m.record_action("fist", "left_click")
    m.stop_recording()
    assert m.rename_macro("old", "new") is True
    assert "new" in m.saved_macros
    assert m.delete_macro("new") is True
    assert "new" not in m.saved_macros


def test_playback_invokes_callback_in_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = MacroRecorder()
    m.start_recording("playme")
    m.record_action("fist", "left_click", (1, 2))
    m.record_action("peace", "volume_up", (3, 4))
    m.stop_recording()

    calls = []
    m.set_playback_speed(4.0)
    assert m.play_macro("playme", lambda g, a, hc: calls.append((g, a, hc))) is True
    assert m.playback_thread is not None
    m.playback_thread.join(timeout=5)
    assert m.is_playing is False
    assert calls[0][0] == "fist"
    assert calls[1][0] == "peace"
    assert calls[0][1] == "left_click"


def test_playback_speed_clamped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = MacroRecorder()
    m.set_playback_speed(100)
    assert m.playback_speed == 4.0
    m.set_playback_speed(0.01)
    assert m.playback_speed == 0.25


def test_stop_recording_empty_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = MacroRecorder()
    m.start_recording("empty")
    assert m.stop_recording() is None
