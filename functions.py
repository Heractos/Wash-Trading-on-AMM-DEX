import pandas as pd
import math
import requests
import json
import numpy as np
from scipy import stats

import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

from web3 import Web3
from web3.middleware import geth_poa_middleware

from hexbytes import HexBytes as hb


def get_bsc_contract_abi(bsc_scan_api_key, bsc_contract_address):
    url = f"""https://api.bscscan.com/api?module=contract&action=getabi&address={bsc_contract_address}&apikey={bsc_scan_api_key}"""
    r = requests.get(url)
    if r.status_code != 200:
        print(f"Request failed in get_bsc_contract_abi: {r.text}")
    # print(r.json()["result"])
    abi = json.loads(r.json()["result"])
    return abi


def get_signatures_from_abi(abi):
    signatures = {}
    for func in [obj for obj in abi if obj["type"] == "event"]:
        name = func["name"]
        types = [input["type"] for input in func["inputs"]]
        signatures[name] = {}
        signatures[name]["function"] = "{}({})".format(name, ",".join(types))

    # signatures
    for event in signatures:
        topic = hb.hex(Web3.sha3(text=signatures[event]["function"]))
        signatures[event]["topic"] = topic
        # popularity = len([i for i in all_topics if i == topic])
        # signatures[event]["popularity"] = popularity
        entry = [
            i for i in [i for i in abi if i["type"] == "event"] if i["name"] == event
        ]
        inputs = [i["name"] for i in entry[0]["inputs"]]
        signatures[event]["inputs"] = inputs
    return signatures


def address_is_contract(address, w3):
    return hb.hex(w3.eth.get_code(Web3.toChecksumAddress(address))) != "0x"


# get pair info
def get_pair_info(
    pair_address, pair_contract_ABI, bsc_scan_api_key, w3=None, token_abi=None
):

    if w3 is None:
        binance_provider = "https://bsc-dataseed.binance.org"
        w3 = Web3(Web3.HTTPProvider(binance_provider))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    pair_contract = w3.eth.contract(
        address=Web3.toChecksumAddress(pair_address), abi=pair_contract_ABI
    )

    kLast = pair_contract.functions.kLast().call()
    reserves = pair_contract.functions.getReserves().call()
    reserve0 = reserves[0]
    reserve1 = reserves[1]
    timestamp = reserves[2]
    if token_abi is None:
        token_abi = get_bsc_contract_abi(
            bsc_scan_api_key, "0x55d398326f99059fF775485246999027B3197955"
        )

    token0_address = pair_contract.functions.token0().call()
    token0_contract = w3.eth.contract(
        address=Web3.toChecksumAddress(token0_address), abi=token_abi
    )
    token0_symbol = token0_contract.functions.symbol().call()
    token0_decimals = token0_contract.functions.decimals().call()

    token1_address = pair_contract.functions.token1().call()
    token1_contract = w3.eth.contract(
        address=Web3.toChecksumAddress(token1_address), abi=token_abi
    )
    token1_symbol = token1_contract.functions.symbol().call()
    token1_decimals = token1_contract.functions.decimals().call()

    pair_info = {
        "pair_contract_address": pair_address,
        "kLast": kLast,
        "reserve0": reserve0,
        "reserve1": reserve1,
        "timestamp": timestamp,
        "token0_address": token0_address,
        "token0_symbol": token0_symbol,
        "token0_decimals": token0_decimals,
        "token1_address": token1_address,
        "token1_symbol": token1_symbol,
        "token1_decimals": token1_decimals,
    }
    # return kLast, reserve0, reserve1, timestamp
    return pair_info


def get_bsc_historical_pancake_swaps(fromBlock, toBlock, bsc_scan_api_key):
    print(f"getting BSC Historical Logs from block {fromBlock} to block {toBlock}...")
    swap_tx_topic = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
    ps_router_v2_topic = (
        "0x00000000000000000000000010ed43c718714eb63d5aa57b78b54704e256024e"
    )
    results = []
    scraped_fully = False
    while not scraped_fully:
        url = f"""https://api.bscscan.com/api?module=logs&action=getLogs&fromBlock={fromBlock}&toBlock={toBlock}&topic0={swap_tx_topic}&topic1={ps_router_v2_topic}&apikey={bsc_scan_api_key}"""
        r = requests.get(url)
        if r.status_code != 200:
            print(f"Request failed in get_bsc_contract_abi: {r.text}")
        results += r.json()["result"]
        scraped_from_block = int(r.json()["result"][0]["blockNumber"], 16)
        scraped_to_block = int(r.json()["result"][-1]["blockNumber"], 16)

        if len(r.json()["result"]) == 1000:
            print(
                f"Found 1000 txs from {scraped_from_block} block to {scraped_to_block} block."
            )
            fromBlock = scraped_to_block
        else:
            scraped_fully = True
            print(
                f"Found {len(r.json()['result'])} txs from {scraped_from_block} block to {scraped_to_block} block. Finishing. Found {len(results)} tx in total"
            )
    return results


def get_bsc_historical_logs(pair_address, fromBlock, toBlock, bsc_scan_api_key):
    print(f"get_bsc_historical_logs from block {fromBlock} to block {toBlock}")
    results = []
    scraped_fully = False
    while not scraped_fully:
        url = f"""https://api.bscscan.com/api?module=logs&action=getLogs&fromBlock={fromBlock}&toBlock={toBlock}&address={pair_address}&apikey={bsc_scan_api_key}"""  # &topic0={topic0}
        r = requests.get(url)
        if r.status_code != 200:
            print(f"Request failed in get_bsc_contract_abi: {r.text}")
        results += r.json()["result"]
        scraped_from_block = int(r.json()["result"][0]["blockNumber"], 16)
        scraped_to_block = int(r.json()["result"][-1]["blockNumber"], 16)

        if len(r.json()["result"]) == 1000:
            print(
                f"Found 1000 txs from {scraped_from_block} block to {scraped_to_block} block. Scraping again from {scraped_to_block} block"
            )
            fromBlock = scraped_to_block
        else:
            scraped_fully = True
            print(
                f"Found {len(r.json()['result'])} txs from {scraped_from_block} block to {scraped_to_block} block. Finishing. Found {len(results)} tx in total"
            )
    return results


def parse_results_dataframe(df, pair_info):
    df.rename(columns={"address": "contract_address"}, inplace=True)
    df["topic"] = df["topics"].apply(
        lambda x: [i for i in x if not "0x000000000000000000000000" in i][0]
    )  # assuming only one such topic can be present in the log
    df["event"] = df["topic"].apply(
        lambda x: [
            i
            for i in pair_info["signatures"]
            if pair_info["signatures"][i]["topic"] == x
        ][0]
    )  # prescribe the event name for it

    # Sync event has no addresses associated
    # Mint has always the same address 10ed43c718714eb63d5...
    df["adresses"] = df[(df.event != "Sync")]["topics"].apply(
        lambda x: [i for i in x if "0x000000000000000000000000" in i]
    )
    df.loc[(df.event != "Sync") & (df.event != "Mint"), "From"] = df[
        (df.event != "Sync") & (df.event != "Mint")
    ]["topics"].apply(
        lambda x: "0x"
        + [i for i in x if "0x000000000000000000000000" in i][0]
        .replace("0x", "")
        .lstrip("0")
        .zfill(40)
    )
    df.loc[(df.event != "Sync") & (df.event != "Mint"), "To"] = df[
        (df.event != "Sync") & (df.event != "Mint")
    ]["topics"].apply(
        lambda x: "0x"
        + [i for i in x if "0x000000000000000000000000" in i][1]
        .replace("0x", "")
        .lstrip("0")
        .zfill(40)
    )  # From and To makes sense for Transfer event, but not so much for Swap events. The swapper will be "To" address. In Swaps, if From and To is the same address - its a simplest swap i think

    # clean up whats redundant
    df.drop(columns=["topics", "adresses", "topic"], inplace=True)

    # turn hex to int
    df["blockNumber"] = df["blockNumber"].apply(lambda x: int(x, 16))
    df["timeStamp"] = df["timeStamp"].apply(lambda x: int(x, 16))
    df["gasPrice"] = df["gasPrice"].apply(lambda x: int(x, 16))
    df["gasUsed"] = df["gasUsed"].apply(lambda x: int(x, 16))

    df.loc[
        df.logIndex == "0x", "logIndex"
    ] = "0x0"  # 0x is not recognised by int("0x",16) function
    df["logIndex"] = df["logIndex"].apply(lambda x: int(x, 16))
    df.loc[
        df.transactionIndex == "0x", "transactionIndex"
    ] = "0x0"  # 0x is not recognised by int("0x",16) function
    df["transactionIndex"] = df["transactionIndex"].apply(lambda x: int(x, 16))

    print(f"Throwing out {len(df.loc[(df.blockNumber =='0x0')])} txs")
    df = df.loc[(df.blockNumber != "0x0")].reset_index(drop=True)

    # make date column
    df["DateTime"] = pd.to_datetime(df["timeStamp"], unit="s")

    # parse swap data (1s for 100 000 txs)
    selection_swap = df.event == "Swap"
    df.loc[selection_swap, "amount0In"] = df.loc[selection_swap]["data"].apply(
        lambda x: int(
            [x.replace("0x", "")[i * 64 : (i + 1) * 64] for i in range(4)][0], 16
        )
    )
    df.loc[selection_swap, "amount1In"] = df.loc[selection_swap]["data"].apply(
        lambda x: int(
            [x.replace("0x", "")[i * 64 : (i + 1) * 64] for i in range(4)][1], 16
        )
    )
    df.loc[selection_swap, "amount0Out"] = df.loc[selection_swap]["data"].apply(
        lambda x: int(
            [x.replace("0x", "")[i * 64 : (i + 1) * 64] for i in range(4)][2], 16
        )
    )
    df.loc[selection_swap, "amount1Out"] = df.loc[selection_swap]["data"].apply(
        lambda x: int(
            [x.replace("0x", "")[i * 64 : (i + 1) * 64] for i in range(4)][3], 16
        )
    )
    return df


def keep_active_adresses(all_swaps, at_least_swaps):
    # drop out addresses that have < at_least_swaps
    active_adresses_df = all_swaps.drop_duplicates("transactionHash")[["To"]]
    for i in range(at_least_swaps - 2):
        filter = active_adresses_df.duplicated(
            "To", keep="first"
        ) & active_adresses_df.duplicated("To", keep="last")
        active_adresses_df = active_adresses_df[filter]  # shrink the adreses df

    all_swaps = all_swaps[
        all_swaps["To"].isin(active_adresses_df.To.to_list())
    ].sort_values(
        "To"
    )  # use these remaining active adresses as filter
    return all_swaps


def plot_addresses(data, target, other, pair_info):

    data["swap_size"] = np.log2(pd.to_numeric(data.amount1In + data.amount1Out + data.amount0In + data.amount0Out))
    
    colour_other_side = {True: "paleturquoise", False: "lightpink"}
    colour_target_side = {True: "green", False: "red"}
    size_buy = {True: 100, False: 30}
    size_sell = {True: 100, False: 30}
    labels = {True: "Transactions", False: "t"}

    sns.set()
    ax = sns.lineplot(
        data=data,
        x="DateTime",
        y="token0_price_in_token1",
        color="black",
        linewidth=0.5,
        alpha=0.3,
    )

    if len(other) > 0:
        if len(other) > 1000:
            other[::10]
        sns.scatterplot(
            data=other,
            x="DateTime",
            y="token0_price_in_token1",
            c=other[f"is_buying"].map(colour_other_side),
            marker="x",
            linewidth=2,
            size="swap_size",
            sizes=(10, 100),
            alpha=0.8,
        )

    if len(target) > 0:
        if len(target) > 1000:
            target[::10]
        ax2 = sns.scatterplot(
            data=target,
            x="DateTime",
            y="token0_price_in_token1",
            edgecolor=target[f"is_buying"].map(colour_target_side),
            facecolors="none",
            linewidth=1,
            size="swap_size",
            sizes=(20, 200),
            alpha=0.8,
        )

    ax.figure.set_size_inches(20, 10)
    ax.set_title(
        f"{pair_info['token1_symbol']} price in {pair_info['token0_symbol']}\nPair: ({pair_info['pair_contract_address']})",
        fontsize=15,
        y=1.05,
    )

    ax.set_ylabel(f"{pair_info['token0_symbol']}")
    ax.set_xlabel("Date")
    legend_elements = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="None",
            label="Target address",
            markerfacecolor="none",
            markeredgecolor=colour_target_side[True],
            markersize=0,
            linewidth=2,
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="None",
            label="Buy transactions",
            markerfacecolor="none",
            markeredgecolor=colour_target_side[True],
            markersize=8,
            linewidth=2,
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="None",
            label=f"Sell transactions",
            markerfacecolor="none",
            markeredgecolor=colour_target_side[False],
            markersize=8,
            linewidth=2,
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="None",
            label="",
            markeredgecolor="None",
            markersize=0,
        ),  # just empty row
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="None",
            label="Other addresses",
            markerfacecolor=colour_target_side[True],
            markeredgecolor="None",
            markersize=0,
        ),
        Line2D(
            [0],
            [0],
            marker="x",
            linestyle="None",
            label="Buy transactions",
            markerfacecolor=colour_other_side[True],
            markeredgecolor=colour_other_side[True],
            markersize=8,
        ),
        Line2D(
            [0],
            [0],
            marker="x",
            linestyle="None",
            label=f"Sell transactions",
            markerfacecolor=colour_other_side[False],
            markeredgecolor=colour_other_side[False],
            markersize=8,
        ),
    ]
    ax.legend(handles=legend_elements, facecolor="white", framealpha=1)
    # plt.savefig(fname = f'images/{pair_info["token1_symbol"]} price in {pair_info["token0_symbol"]}.png')
    plt.show()