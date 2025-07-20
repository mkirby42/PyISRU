docker run \
  --name cloudflared \
  --network flask-net \
  --restart=always \
  cloudflare/cloudflared:latest \
  --no-autoupdate tunnel run \
  --token  \
  --url http://flask-app:8000

docker build -t pyisru .   
docker run -d -p 8000:8000 --name flask-app --network flask-net pyisru