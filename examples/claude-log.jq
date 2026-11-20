fromjson?
| if .type == "system" and .subtype == "init" then
    "Claude Code started"
  elif .type == "assistant" then
    .message.content[] | select(.type == "tool_use") | "Read " + .input.file_path
  elif .type == "result" then
    "", (.result // (.errors[]?))
  else empty
  end
