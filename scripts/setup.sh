#!/usr/bin/env bash
# Setups the repository.

# Stop on errors
set -e

cd "$(dirname "$0")/.."

# Add default vscode settings if not existing
SETTINGS_FILE=./.vscode/settings.json
SETTINGS_TEMPLATE_FILE=./.vscode/settings.default.jsonc
if [ ! -f "$SETTINGS_FILE" ] && [ -f "$SETTINGS_TEMPLATE_FILE" ]; then
    echo "Copy $SETTINGS_TEMPLATE_FILE to $SETTINGS_FILE."
    cp "$SETTINGS_TEMPLATE_FILE" "$SETTINGS_FILE"
fi

mkdir -p config

# Install uv outside .venv, since `uv sync` would remove it from the venv.
export PATH="$HOME/.local/bin:$PATH"
if ! [ -x "$(command -v uv)" ]; then
  UV_HOME="$HOME/.local/share/uv-venv"
  python3 -m venv "$UV_HOME"
  "$UV_HOME/bin/pip" install uv
  mkdir -p "$HOME/.local/bin"
  ln -sf "$UV_HOME/bin/uv" "$HOME/.local/bin/uv"
fi

if [ ! -n "$VIRTUAL_ENV" ]; then
  if [ -x "$(command -v uv)" ]; then
    uv venv .venv
  else
    python3 -m venv .venv
  fi
  source .venv/bin/activate
fi

touch "$HOME/.bashrc"
VENV_ACTIVATION="$PWD/.venv/bin/activate"
if ! grep -Fqx "source \"$VENV_ACTIVATION\"" "$HOME/.bashrc"; then
  printf '\nsource "%s"\n' "$VENV_ACTIVATION" >> "$HOME/.bashrc"
fi

scripts/bootstrap.sh
