# API Provider Manager

A professional Tkinter-based GUI application for managing AI API provider credentials and settings on Windows.

## Features

- **Multi-Provider Support**: Manage credentials for OpenRouter, OpenAI, Anthropic, Google Gemini, Ollama, Strata, and Custom providers
- **Secure Encryption**: Windows DPAPI encryption for API keys (with fallback to base64 on non-Windows systems)
- **Model Management**: Fetch, search, and select models from each provider
- **Settings Persistence**: Local JSON-based configuration storage with secure file permissions
- **Import/Export**: Backup and restore your API provider settings
- **Connection Testing**: Verify API connectivity before use
- **API Key Manager**: Dedicated key management with view, copy, edit notes, backup, and restore functionality
- **Intelligent Caching**: 1-hour model cache to avoid repeated API calls
- **Background Sync**: Auto-refresh models every 15 minutes
- **Recently Used**: Track last 10 used models per provider
- **Keyboard Shortcuts**: Ctrl+S (save), Ctrl+T (test), Ctrl+F (search)
- **Light Theme UI**: Clean, professional interface with responsive layout

## Requirements

- Python 3.8+
- Windows 10/11 (or Linux/macOS with base64 fallback)
- tkinter (usually included with Python)
- requests library

## Installation

1. Extract all files from the zip package
2. Install required dependencies:
   ```bash
   pip install requests
   ```

## Usage

Run the application:
```bash
python main.py
```

### Workflow

1. **Select Provider**: Choose an API provider from the dropdown
2. **Configure**: Enter Base URL and API Key
3. **Fetch Models**: Click "Fetch Models" to retrieve available models
4. **Search Models**: Use the search field to filter models
5. **Select Model**: Click on a model in the list to select it
6. **Save**: Click "Save" to persist your settings
7. **Test**: Use "Test Connection" to verify your credentials

### Key Manager

Click the **🔑 Key Manager** button to open the dedicated key management window:

- **View Keys**: List all saved API keys by provider
- **View/Copy**: View actual key value and copy to clipboard
- **Edit Notes**: Add or edit notes for each key
- **Export Keys**: Export all keys to encrypted JSON file
- **Import Keys**: Import keys from backup file
- **Backup**: Create timestamped backup of all keys
- **Restore**: Restore keys from previous backups
- **Search**: Search keys by provider name or notes

### File Descriptions

- **main.py**: Application entry point
- **gui.py**: Tkinter GUI implementation with main window
- **key_manager.py**: API key storage, encryption, backup, and restore functionality
- **key_manager_gui.py**: GUI window for managing API keys
- **api_client.py**: API communication and model fetching with latency tracking
- **settings_manager.py**: Configuration persistence with encryption and model caching
- **encryption.py**: Windows DPAPI encryption utilities
- **constants.py**: Provider configurations and paths
- **launch.bat**: Windows batch file to launch the application

## Configuration

Settings are stored in:
```
~/.api_provider_manager/providers.json
```

This directory and file are created automatically on first run.

## Security Notes

- API keys are encrypted using Windows DPAPI on Windows systems
- On non-Windows systems, keys are base64-encoded
- Config file permissions are set to 0o600 (read/write owner only)
- Never commit your providers.json to version control

## License

Provided as-is for managing API provider credentials.
