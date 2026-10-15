FROM binwiederhier/ntfy:latest
# Render injects $PORT at runtime; ntfy honors NTFY_* env vars.
# Clear the image ENTRYPOINT so the shell form runs as intended.
ENTRYPOINT []
CMD ["sh", "-c", "NTFY_LISTEN_HTTP=0.0.0.0:$PORT exec ntfy serve"]
