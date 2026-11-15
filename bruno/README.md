# bruno — API collections

[Bruno](https://www.usebruno.com/) collections for poking at the local APIs by
hand. Files are plain YAML, so they diff cleanly.

```
bruno/
├── yt/                     requests used while building the YouTube scraper
│                           (Untitled 1…27.yml + opencollection.yml)
└── Sample API Collection/  the collection Bruno ships with (Get Users)
```

## Use

1. Open Bruno → *Open Collection* → pick `bruno/yt`.
2. Select the environment in `yt/` if one is defined, start the service you want
   to hit (`whatsapp_bot` on :3000, `mission2026` on :8001), then send.

## Notes

- These are scratch requests, not a test suite. Nothing runs them automatically.
- Committed to git — keep secrets out of the `.yml` files and use Bruno
  environments for tokens.
