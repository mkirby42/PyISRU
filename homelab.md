docker run \
  --name cloudflared \
  --network flask-net \
  cloudflare/cloudflared:latest \
  --no-autoupdate tunnel run \
  --token eyJhIjoiZmI5OGNiMTliMjEwZDkzYmE1NzIxODdlMGVhNjBkZjQiLCJ0IjoiZTI3YTliYmQtZDU1Zi00ZDI1LWJiOWEtYzM0NDRjNDk3MmMzIiwicyI6Ik5HVTJOemd4WVRJdE1qUTNOQzAwWW1ZMkxUa3dNamN0WVRrMFpUY3daR0UwWldSbCJ9 \
  --url http://flask-app:8000

docker run -d -p 8000:8000 --name flask-app --network flask-net pyisru