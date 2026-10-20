#!/bin/sh
# starts mocks + server with a fresh home (for running one suite by hand)
cd "$(dirname "$0")"
for f in server.pid mock.pid cloud.pid images.pid; do [ -f $f ] && kill $(cat $f) 2>/dev/null; done
sleep 0.5; rm -rf home work fake_claude_calls.jsonl; mkdir work
export MARCHAND_HOME=$PWD/home OLLAMA_HOST=http://127.0.0.1:11555 MARCHAND_CLAUDE=$PWD/fake_claude.py MARCHAND_OPEN_LOG=$PWD/open_urls.log MARCHAND_FT_CMD="python3 $PWD/fake_trainer.py"
nohup python3 mock.py > mock.log 2>&1 & echo $! > mock.pid
nohup python3 mock_cloud.py > cloud.log 2>&1 & echo $! > cloud.pid
nohup python3 mock_images.py > images.log 2>&1 & echo $! > images.pid
sleep 0.8
nohup python3 ../server.py --no-browser > server.log 2>&1 & echo $! > server.pid
sleep 1.5
