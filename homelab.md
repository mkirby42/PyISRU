docker run \
  --name cloudflared \
  --network flask-net \
  cloudflare/cloudflared:latest \
  --no-autoupdate tunnel run \
  --token  \
  --url http://flask-app:8000

docker run -d -p 8000:8000 --name flask-app --network flask-net pyisru