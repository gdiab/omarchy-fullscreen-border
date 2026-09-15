-- Run the actual Lua module against small theme fixtures, with filesystem and
-- compositor boundaries stubbed. No real desktop or user files are touched.
local open, rename, getenv = io.open, os.rename, os.getenv
local root = (arg[0]:match("^(.*)/tests/[^/]+$") or ".")
local function check(theme, active, expected)
  local output, rules = "", {}
  os.getenv = function(key) return key == "HOME" and "/test-home" or getenv(key) end
  io.open = function(path, mode)
    if path:match("colors%.toml$") then
      return {lines = function() return theme:gmatch("[^\n]+") end, close = function() end}
    end
    if mode == "r" then return nil end
    assert(path == "/test-home/.local/state/omarchy/fullscreen-border.json.tmp")
    return {write = function(_, text) output = text end, close = function() end}
  end
  os.rename = function() return true end
  hl = {
    get_config = function(key)
      return {colors = key == "general.col.active_border" and active or {"0xaa595959"}}
    end,
    window_rule = function(rule) table.insert(rules, rule) end,
  }
  dofile(root .. "/hypr/fullscreen-border.lua")
  assert(output:find('"color":"#' .. expected .. '"', 1, true), output)
  assert(#rules == 3)
  assert(rules[1].border_color == "rgb(" .. expected .. ") rgb(" .. expected .. ")")
  assert(rules[2].border_size == 5 and rules[3].border_size == 5)
  assert(rules[2].border_color ~= rules[3].border_color, "Attention must still pulse")
end
check('background = "#0B0C16"\nblue = "#829dd4"\nmagenta = "#86a7df"',
      {"0xee26a269", "0xee2ec27e"}, "829dd4")
check('background = "#1e1e2e"\nblue = "#89b4fa"\nmagenta = "#f5c2e7"',
      {"0xff89b4fa"}, "f5c2e7")
-- Matching any gradient stop excludes a color, even if it is not the first.
check('background = "#101315"\nblue = "#829dd4"\nmagenta = "#f5c2e7"',
      {"0xff26a269", "0xff829dd4"}, "f5c2e7")
check('background = "#faf4ed"\nblue = "#faf4ed"\nmagenta = "#bd5379"',
      {"0xff56949f"}, "bd5379")
io.open, os.rename, os.getenv = open, rename, getenv
print("4 palette/gradient/light-theme and attention-pulse cases passed.")
