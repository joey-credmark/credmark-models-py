# pylint:disable=unused-import,line-too-long

import argparse
import logging
import os
import sys
import unittest
import testtools
import inspect
from concurrencytest import ConcurrentTestSuite, fork_for_tests
from importlib import import_module

from cmk_test import CMKTest

from test_aave import TestAAVE
from test_chainlink import TestChainlink
from test_cmk import TestCMK
from test_compose import TestCompose
from test_compound import TestCompound
from test_curve import TestCurve
from test_dashboard import TestDashboard
from test_example import TestExample
from test_finance import TestFinance
from test_price import TestPrice
from test_speed import TestSpeed
from test_sushiswap import TestSushiSwap
from test_token import TestToken
from test_tvl import TestTVL
from test_uniswap import TestUniswap


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level='INFO')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('type', type=str, default='prod',
                        help=('Test type: \n'
                              '- prod(local model + gw)\n'
                              '- test(local gw)\n'
                              '- gw (official gateway only'))
    parser.add_argument('start_n', type=int, default=0,
                        help=('case number to start'))
    parser.add_argument('-b', '--block_number', type=int, default=14249443,
                        help=('Block number to run'))
    parser.add_argument('-s', '--serial', action='store_true', default=False,
                        help=('Run tests in serial'))

    args = vars(parser.parse_args())
    CMKTest.type = args['type']

    if args['type'] == 'test':
        sys.path.insert(0, os.path.join('..', 'credmark-model-framework-py'))
        CMKTest.post_flag = ['-l', '-', '--api_url=http://localhost:8700']
        CMKTest.pre_flag = ['--model_path', 'x']
    elif args['type'] == 'prod':
        CMKTest.post_flag = []
        CMKTest.pre_flag = []
    elif args['type'] == 'gw':
        CMKTest.post_flag = ['-l', '-']
        CMKTest.pre_flag = ['--model_path', 'x']
    else:
        print(f'Unknown test type {args["type"]}')
        sys.exit()

    CMKTest.test_main = import_module('credmark.cmf.credmark_dev')
    mod_model_api = import_module('credmark.cmf.engine.model_api')
    mod_model_api.RUN_REQUEST_TIMEOUT = 6400  # type: ignore

    CMKTest.block_number = args["block_number"]
    CMKTest.start_n = args["start_n"]

    # token_price_deps='price.quote,price.quote,uniswap-v2.get-weighted-price,uniswap-v3.get-weighted-price,sushiswap.get-weighted-price,uniswap-v3.get-pool-info'
    # var_deps=finance.var-engine,finance.var-reference,price.quote,finance.get-one,${token_price_deps}

    allTests = [o for _n, o in locals().items() if inspect.isclass(o) and issubclass(o, CMKTest)]
    suites = unittest.TestSuite([unittest.TestLoader().loadTestsFromTestCase(x) for x in allTests])

    runner = unittest.TextTestRunner()
    if args['serial']:
        runner.run(suites)
        # sys.argv = sys.argv[:1]
        # unittest.main(failfast=True)
    else:
        concurrent_suite = ConcurrentTestSuite(suites, fork_for_tests(20))
        runner.run(concurrent_suite)
