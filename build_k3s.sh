docker build -t js-bot:latest .

docker save js-bot:latest | sudo k3s ctr images import -
