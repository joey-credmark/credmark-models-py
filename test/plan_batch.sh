python test/test.py run finance.historical-plan -i '{"model_slug": "chainlink.eth-usd", "model_input": {}, "asOf": "2022-05-13", "window": "730 days", "interval": "1 day", "input_keys": [], "save_file":"tmp/weth_730day_oracle"}' -b 14783373 -j --api_url=http://192.168.68.122:8700 -l "*"

exit

python test/test.py run finance.historical-plan -i '{"model_slug": "aave-v2.get-oracle-price", "model_input": {"symbol": "WETH"}, "asOf": "2022-05-13", "window": "730 days", "interval": "1 day", "input_keys": ["WETH"], "save_file":"tmp/weth_730day_oracle"}' -b 14783373 -j --api_url=http://192.168.68.122:8700 # -l "*"
exit

python test/test.py run finance.historical-plan -i '{"model_slug": "token.price", "model_input": {"symbol": "WETH"}, "asOf": "2022-05-13", "window": "365 days", "interval": "1 day", "input_keys": ["WETH"], "save_file":"tmp/weth_365day"}' -b 14783373 -j --api_url=http://192.168.68.122:8700 # -l "*"

python test/test.py run finance.historical-plan -i '{"model_slug": "finance.min-risk-rate", "model_input": {}, "asOf": "2022-05-13", "window": "10 days", "interval": "1 day", "input_keys": ["WETH"], "save_file":"tmp/mrr_10day"}' -b 14783373 -j --api_url=http://192.168.68.122:8700 # -l "*"

python test/test.py run finance.historical-plan -i '{"model_slug": "finance.min-risk-rate", "model_input": {}, "asOf": "2022-05-13", "window": "50 days", "interval": "1 day", "input_keys": ["WETH"], "save_file":"tmp/mrr_50day"}' -b 14783373 -j --api_url=http://192.168.68.122:8700 # -l "*"

python test/test.py run finance.historical-plan -i '{"model_slug": "token.price", "model_input": {"symbol": "WBTC"}, "asOf": "2022-05-13", "window": "365 days", "interval": "1 day", "input_keys": ["WBTC"], "save_file":"tmp/wbtc_365day"}' -b 14783373 -j --api_url=http://192.168.68.122:8700 # -l "*"
