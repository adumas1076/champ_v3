# Tests for Brain Loop Selector

from brain.loop_selector import LoopSelector, LoopType


selector = LoopSelector()


# ---- AUTONOMOUS triggers ----

def test_autonomous_build_me():
    assert selector.select("build me a web scraper") == LoopType.AUTONOMOUS

def test_autonomous_go_do():
    assert selector.select("go do that research for me") == LoopType.AUTONOMOUS

def test_autonomous_self_mode():
    assert selector.select("use self mode to handle this") == LoopType.AUTONOMOUS

def test_autonomous_automate():
    assert selector.select("automate my morning routine") == LoopType.AUTONOMOUS

def test_autonomous_create_pipeline():
    assert selector.select("create a data pipeline for me") == LoopType.AUTONOMOUS

def test_autonomous_set_up_system():
    assert selector.select("set up the integration system") == LoopType.AUTONOMOUS


# ---- HANDOFF triggers ----

def test_handoff_get_billy():
    assert selector.select("get billy to handle this") == LoopType.HANDOFF

def test_handoff_switch_to():
    assert selector.select("switch to genesis") == LoopType.HANDOFF

def test_handoff_delegate():
    assert selector.select("delegate this to sadie") == LoopType.HANDOFF

def test_handoff_let_handle():
    assert selector.select("let genesis handle the research") == LoopType.HANDOFF


# ---- VERIFY triggers ----

def test_verify_and_check():
    assert selector.select("run the script and check if it worked") == LoopType.VERIFY

def test_verify_make_sure():
    assert selector.select("make sure the form submitted correctly") == LoopType.VERIFY

def test_verify_double_check():
    assert selector.select("double check that output") == LoopType.VERIFY


# ---- ACTION triggers ----

def test_action_open_app():
    assert selector.select("open spotify for me") == LoopType.ACTION

def test_action_google():
    assert selector.select("google the latest AI news") == LoopType.ACTION

def test_action_screenshot():
    assert selector.select("take a screenshot") == LoopType.ACTION

def test_action_browse():
    # "check" triggers VERIFY — correct behavior, verify wins over action
    assert selector.select("go to the website and look at the pricing page") == LoopType.ACTION

def test_action_fill_form():
    assert selector.select("fill out the contact form") == LoopType.ACTION

def test_action_weather():
    assert selector.select("what's the weather in Houston") == LoopType.ACTION

def test_action_run_code():
    assert selector.select("run this code for me") == LoopType.ACTION


# ---- DIRECT triggers ----

def test_direct_what_is():
    assert selector.select("what is a neural network") == LoopType.DIRECT

def test_direct_explain():
    assert selector.select("explain the difference between TCP and UDP") == LoopType.DIRECT

def test_direct_yes():
    assert selector.select("yes") == LoopType.DIRECT

def test_direct_thoughts():
    assert selector.select("thoughts?") == LoopType.DIRECT

def test_direct_empty():
    assert selector.select("") == LoopType.DIRECT


# ---- Priority: more specific wins ----

def test_priority_autonomous_over_action():
    # "build me a scraper" has both "build me" (autonomous) and implicit action
    assert selector.select("build me a scraper tool") == LoopType.AUTONOMOUS

def test_priority_handoff_over_action():
    # "get billy to open the browser" has both handoff and action signals
    assert selector.select("get billy to open the browser") == LoopType.HANDOFF


# ---- Instructions ----

def test_instructions_exist():
    for loop_type in [LoopType.DIRECT, LoopType.ACTION, LoopType.VERIFY,
                      LoopType.AUTONOMOUS, LoopType.HANDOFF]:
        instruction = selector.get_instruction(loop_type)
        assert instruction, f"No instruction for {loop_type}"
        assert "[LOOP:" in instruction

def test_internal_loops_no_instruction():
    # Healing, Memory, Watch are internal — no user-facing instruction
    for loop_type in [LoopType.HEALING, LoopType.MEMORY, LoopType.WATCH]:
        assert selector.get_instruction(loop_type) == ""