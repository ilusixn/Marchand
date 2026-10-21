#!/bin/sh
# usage: run_all.sh  (starts mocks + server with a fresh home, runs API and UI suites)
cd "$(dirname "$0")"
for f in server.pid mock.pid cloud.pid images.pid; do [ -f $f ] && kill $(cat $f) 2>/dev/null; done
sleep 0.5; rm -rf home work *.png; mkdir work
export MARCHAND_HOME=$PWD/home OLLAMA_HOST=http://127.0.0.1:11555 MARCHAND_CLAUDE=$PWD/fake_claude.py MARCHAND_STRATA=$PWD/fake_strata.py MARCHAND_OPEN_LOG=$PWD/open_urls.log MARCHAND_FT_CMD="python3 $PWD/fake_trainer.py"
rm -f fake_claude_calls.jsonl
nohup python3 mock.py > mock.log 2>&1 & echo $! > mock.pid
nohup python3 mock_cloud.py > cloud.log 2>&1 & echo $! > cloud.pid
nohup python3 mock_images.py > images.log 2>&1 & echo $! > images.pid
sleep 0.8
nohup python3 ../server.py --no-browser > server.log 2>&1 & echo $! > server.pid
sleep 1.5
echo "== curriculum verification (every task fails before, passes after)"; python3 verify_curriculum.py | tail -3
echo "== API suite 1"; python3 api_test.py $PWD/work | tail -1
echo "== API suite 2"; python3 api_test2.py $PWD/work | tail -1
kill $(cat server.pid); sleep 0.5; rm -rf home fake_claude_calls.jsonl
nohup python3 ../server.py --no-browser > server.log 2>&1 & echo $! > server.pid
sleep 1.5
echo "== API suite 3 (Claude bridge, training, files, video)"; python3 api_test3.py $PWD/work | grep -v "^PASS"
# fresh state for the UI suite
kill $(cat server.pid); sleep 0.5; rm -rf home; mkdir -p work
nohup python3 ../server.py --no-browser > server.log 2>&1 & echo $! > server.pid
sleep 1.5
echo "== UI end-to-end"; timeout 900 python3 ui_e2e.py $PWD/work
code=$?
for f in server.pid mock.pid cloud.pid images.pid; do kill $(cat $f) 2>/dev/null; done
exit $code
