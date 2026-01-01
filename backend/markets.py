"""Predefined market tickers - Extended lists"""

# Asset type categories
ASSET_TYPES = {
    "stocks": ["hongkong", "cac40", "sp500", "tech", "dividend", "nasdaq100", "europe", "emerging"],
    "etfs": ["etfs", "crypto_etfs"],
    "crypto": ["crypto"]
}

MARKETS = {
    "hongkong": {
        "name": "Hong Kong",
        "type": "stocks",
        "tickers": [
            "0700.HK",  # Tencent
            "0005.HK",  # HSBC
            "0941.HK",  # China Mobile
            "1299.HK",  # AIA Group
            "0388.HK",  # HK Exchanges
            "2318.HK",  # Ping An Insurance
            "0001.HK",  # CK Hutchison
            "0003.HK",  # CK Infrastructure
            "0011.HK",  # Hang Seng Bank
            "0016.HK",  # Sun Hung Kai
            "0002.HK",  # CLP Holdings
            "0006.HK",  # Power Assets
            "0012.HK",  # Henderson Land
            "0017.HK",  # New World Dev
            "0019.HK",  # Swire Pacific
            "0023.HK",  # Bank of East Asia
            "0027.HK",  # Galaxy Entertainment
            "0066.HK",  # MTR Corporation
            "0083.HK",  # Sino Land
            "0101.HK",  # Hang Lung Properties
            "0175.HK",  # Geely Auto
            "0241.HK",  # Alibaba Health
            "0267.HK",  # CITIC
            "0288.HK",  # WH Group
            "0291.HK",  # China Resources Beer
            "0316.HK",  # Orient Overseas
            "0386.HK",  # China Petroleum
            "0388.HK",  # HKEX
            "0669.HK",  # Techtronic Industries
            "0688.HK",  # China Overseas Land
            "0762.HK",  # China Unicom
            "0823.HK",  # Link REIT
            "0857.HK",  # PetroChina
            "0883.HK",  # CNOOC
            "0939.HK",  # CCB
            "0960.HK",  # Longfor Group
            "0968.HK",  # Xinyi Solar
            "0981.HK",  # SMIC
            "1038.HK",  # CK Asset
            "1044.HK",  # Hengan International
            "1088.HK",  # China Shenhua
            "1093.HK",  # CSPC Pharmaceutical
            "1109.HK",  # China Resources Land
            "1113.HK",  # CK Asset
            "1177.HK",  # Sino Biopharmaceutical
            "1211.HK",  # BYD Company
            "1288.HK",  # ABC
            "1398.HK",  # ICBC
            "1810.HK",  # Xiaomi
            "1876.HK",  # Budweiser APAC
            "1928.HK",  # Sands China
            "1997.HK",  # Wharf REIC
            "2007.HK",  # Country Garden
            "2018.HK",  # AAC Technologies
            "2020.HK",  # ANTA Sports
            "2269.HK",  # WuXi Biologics
            "2313.HK",  # Shenzhou International
            "2319.HK",  # Mengniu Dairy
            "2331.HK",  # Li Ning
            "2382.HK",  # Sunny Optical
            "2388.HK",  # BOC Hong Kong
            "2628.HK",  # China Life
            "2688.HK",  # ENN Energy
            "2899.HK",  # Zijin Mining
            "3328.HK",  # Bank of Communications
            "3333.HK",  # Evergrande
            "3690.HK",  # Meituan
            "3968.HK",  # China Merchants Bank
            "3988.HK",  # Bank of China
            "6098.HK",  # Country Garden Services
            "6862.HK",  # Haidilao
            "9618.HK",  # JD.com
            "9633.HK",  # Nongfu Spring
            "9888.HK",  # Baidu
            "9901.HK",  # New Oriental Education
            "9988.HK",  # Alibaba
            "9999.HK",  # NetEase
        ]
    },
    "cac40": {
        "name": "CAC 40",
        "type": "stocks",
        "tickers": [
            "MC.PA",   # LVMH
            "OR.PA",   # L'Oreal
            "SAN.PA",  # Sanofi
            "AI.PA",   # Air Liquide
            "TTE.PA",  # TotalEnergies
            "BNP.PA",  # BNP Paribas
            "SU.PA",   # Schneider Electric
            "CS.PA",   # AXA
            "DG.PA",   # Vinci
            "RMS.PA",  # Hermes
            "KER.PA",  # Kering
            "SAF.PA",  # Safran
            "AIR.PA",  # Airbus
            "EL.PA",   # EssilorLuxottica
            "RI.PA",   # Pernod Ricard
            "CAP.PA",  # Capgemini
            "DSY.PA",  # Dassault Systemes
            "EN.PA",   # Bouygues
            "ENGI.PA", # Engie
            "GLE.PA",  # Societe Generale
            "LR.PA",   # Legrand
            "ML.PA",   # Michelin
            "ORA.PA",  # Orange
            "PUB.PA",  # Publicis
            "SGO.PA",  # Saint-Gobain
            "STLA.PA", # Stellantis
            "STM.PA",  # STMicroelectronics
            "TEP.PA",  # Teleperformance
            "URW.PA",  # Unibail-Rodamco
            "VIE.PA",  # Veolia
            "VIV.PA",  # Vivendi
            "WLN.PA",  # Worldline
            "AC.PA",   # Accor
            "ACA.PA",  # Credit Agricole
            "ATO.PA",  # Atos
            "BN.PA",   # Danone
            "CA.PA",   # Carrefour
            "ERF.PA",  # Eurofins
            "FP.PA",   # Total
            "HO.PA",   # Thales
        ]
    },
    "sp500": {
        "name": "S&P 500 Top 100",
        "type": "stocks",
        "tickers": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "UNH", "JNJ",
            "V", "XOM", "JPM", "WMT", "MA", "PG", "CVX", "HD", "LLY", "ABBV",
            "MRK", "PEP", "KO", "COST", "AVGO", "PFE", "TMO", "MCD", "CSCO", "ACN",
            "ABT", "DHR", "NEE", "VZ", "ADBE", "CRM", "NKE", "TXN", "CMCSA", "PM",
            "INTC", "ORCL", "WFC", "BMY", "UPS", "RTX", "MS", "QCOM", "T", "HON",
            "BA", "AMGN", "UNP", "LOW", "SPGI", "IBM", "GS", "CAT", "SBUX", "DE",
            "ELV", "CVS", "INTU", "BLK", "AXP", "GILD", "AMD", "LMT", "MDLZ", "ADI",
            "ISRG", "BKNG", "REGN", "C", "PLD", "VRTX", "ADP", "TJX", "SYK", "TMUS",
            "ZTS", "CI", "MMC", "NOW", "CME", "SCHW", "MO", "DUK", "SO", "BDX",
            "CB", "CL", "FISV", "EOG", "NOC", "USB", "PNC", "ITW", "APD", "ICE",
        ]
    },
    "tech": {
        "name": "Tech Giants",
        "type": "stocks",
        "tickers": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "CRM", "ORCL",
            "INTC", "CSCO", "ADBE", "QCOM", "TXN", "AVGO", "NOW", "IBM", "INTU", "AMAT",
            "MU", "LRCX", "ADI", "KLAC", "SNPS", "CDNS", "MRVL", "NXPI", "FTNT", "PANW",
            "CRWD", "ZS", "DDOG", "NET", "SNOW", "PLTR", "U", "TWLO", "OKTA", "ZM",
            "DOCU", "SPLK", "WDAY", "VEEV", "HUBS", "TTD", "ROKU", "SQ", "PYPL", "SHOP",
            "SE", "MELI", "BABA", "JD", "PDD", "BIDU", "NTES", "TME", "BILI", "IQ",
            "UBER", "LYFT", "ABNB", "DASH", "COIN", "HOOD", "RBLX", "MTCH", "PINS", "SNAP",
            "SPOT", "NFLX", "DIS", "PARA", "WBD", "CMCSA", "CHTR", "TMUS", "VZ", "T",
            "DELL", "HPQ", "HPE", "NTAP", "WDC", "STX", "PSTG", "NEWR", "ESTC", "MDB",
            "TEAM", "ATLG", "GTLB", "FROG", "CFLT", "PATH", "AI", "BBAI", "UPST", "AFRM",
        ]
    },
    "dividend": {
        "name": "Dividend Aristocrats",
        "type": "stocks",
        "tickers": [
            "JNJ", "PG", "KO", "PEP", "MMM", "ABT", "MCD", "XOM", "CVX", "T",
            "VZ", "IBM", "CL", "GPC", "SWK", "EMR", "DOV", "PPG", "SHW", "ADP",
            "AFL", "CINF", "CB", "TGT", "WMT", "LOW", "SYY", "GWW", "CTAS", "NUE",
            "BEN", "TROW", "AOS", "ITW", "HRL", "CLX", "MKC", "CAH", "CHRW", "FRT",
            "ED", "O", "WBA", "LEG", "APD", "LIN", "CAT", "GD", "ROP", "ECL",
            "BDX", "MDT", "EXPD", "PNR", "ESS", "ALB", "SPGI", "BRO", "WST", "STE",
            "ATR", "ATO", "NEE", "DUK", "SO", "AEP", "XEL", "WEC", "DTE", "CMS",
            "LNT", "EVRG", "NI", "PEG", "PPL", "FE", "AEE", "CNP", "AWK", "WTRG",
        ]
    },
    "nasdaq100": {
        "name": "NASDAQ 100",
        "type": "stocks",
        "tickers": [
            "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "PEP",
            "COST", "ADBE", "CSCO", "NFLX", "CMCSA", "TMUS", "AMD", "TXN", "INTC", "QCOM",
            "HON", "INTU", "AMGN", "AMAT", "BKNG", "ISRG", "SBUX", "ADP", "MDLZ", "GILD",
            "VRTX", "ADI", "REGN", "LRCX", "MU", "PYPL", "KLAC", "SNPS", "CDNS", "PANW",
            "MELI", "ORLY", "MAR", "ABNB", "ASML", "CTAS", "CSX", "CHTR", "MNST", "FTNT",
            "MRVL", "NXPI", "WDAY", "KDP", "PCAR", "DXCM", "KHC", "ODFL", "AEP", "CPRT",
            "EXC", "PAYX", "MCHP", "LULU", "ROST", "IDXX", "ON", "FAST", "VRSK", "CTSH",
            "AZN", "CEG", "CSGP", "CRWD", "DDOG", "XEL", "EA", "BKR", "GEHC", "FANG",
            "BIIB", "DLTR", "ZS", "ANSS", "ILMN", "TEAM", "WBD", "ALGN", "SIRI", "JD",
            "ZM", "EBAY", "ENPH", "LCID", "RIVN", "MRNA", "WBA", "SGEN", "SPLK", "OKTA",
        ]
    },
    "europe": {
        "name": "Europe Top",
        "type": "stocks",
        "tickers": [
            # Germany (DAX)
            "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "BAS.DE", "BAYN.DE", "BMW.DE", "MBG.DE", "VOW3.DE", "ADS.DE",
            "MUV2.DE", "DBK.DE", "IFX.DE", "HEN3.DE", "RWE.DE", "EON.DE", "FRE.DE", "DPW.DE", "CON.DE", "MTX.DE",
            # UK (FTSE)
            "SHEL.L", "AZN.L", "HSBA.L", "ULVR.L", "BP.L", "GSK.L", "RIO.L", "DGE.L", "REL.L", "LLOY.L",
            "BARC.L", "VOD.L", "NG.L", "BT-A.L", "AAL.L", "STAN.L", "PRU.L", "LGEN.L", "IMB.L", "SSE.L",
            # Switzerland
            "NESN.SW", "ROG.SW", "NOVN.SW", "UBSG.SW", "CSGN.SW", "ABB.SW", "ZURN.SW", "SREN.SW", "LONN.SW", "GIVN.SW",
            # Netherlands
            "ASML.AS", "INGA.AS", "PHIA.AS", "UNA.AS", "AD.AS", "HEIA.AS", "ABN.AS", "RAND.AS", "WKL.AS", "AKZA.AS",
        ]
    },
    "emerging": {
        "name": "Emerging Markets",
        "type": "stocks",
        "tickers": [
            # China ADRs
            "BABA", "JD", "PDD", "BIDU", "NIO", "XPEV", "LI", "BILI", "TME", "IQ",
            # India
            "INFY", "WIT", "HDB", "IBN", "SIFY", "TTM", "VEDL", "RDY", "WNS", "MMYT",
            # Brazil
            "VALE", "PBR", "ITUB", "BBD", "ABEV", "SBS", "EWZ", "GGB", "SID", "BRFS",
            # Korea
            "005930.KS", "000660.KS", "035420.KS", "005380.KS", "051910.KS",
            # Taiwan
            "TSM", "UMC", "ASX", "AEHR", "HIMX",
            # South Africa
            "NPN.JO", "SOL.JO", "SBK.JO", "AGL.JO", "BHP.JO",
            # Mexico
            "AMX", "FEMSA", "BSMX", "OMAB", "ASUR",
        ]
    },
    "etfs": {
        "name": "ETFs Populaires",
        "type": "etfs",
        "tickers": [
            # US Market ETFs
            "SPY",   # S&P 500
            "QQQ",   # NASDAQ 100
            "DIA",   # Dow Jones
            "IWM",   # Russell 2000
            "VTI",   # Total Stock Market
            "VOO",   # Vanguard S&P 500
            "IVV",   # iShares S&P 500
            "VUG",   # Vanguard Growth
            "VTV",   # Vanguard Value
            "SCHD",  # Schwab US Dividend
            # Sector ETFs
            "XLK",   # Technology
            "XLF",   # Financials
            "XLE",   # Energy
            "XLV",   # Healthcare
            "XLI",   # Industrials
            "XLY",   # Consumer Discretionary
            "XLP",   # Consumer Staples
            "XLU",   # Utilities
            "XLRE",  # Real Estate
            "XLB",   # Materials
            # Thematic ETFs
            "ARKK",  # ARK Innovation
            "ARKG",  # ARK Genomic
            "ARKF",  # ARK Fintech
            "ARKW",  # ARK Next Gen Internet
            "ARKQ",  # ARK Autonomous Tech
            "ICLN",  # Clean Energy
            "TAN",   # Solar
            "LIT",   # Lithium & Battery
            "BOTZ",  # Robotics & AI
            "HACK",  # Cybersecurity
            "SKYY",  # Cloud Computing
            "FINX",  # Fintech
            "ROBO",  # Robotics
            "AIQ",   # AI & Big Data
            "WCLD",  # Cloud Computing
            # International ETFs
            "VEA",   # Developed Markets
            "VWO",   # Emerging Markets
            "EFA",   # EAFE
            "EEM",   # Emerging Markets
            "FXI",   # China Large Cap
            "MCHI",  # MSCI China
            "EWJ",   # Japan
            "EWG",   # Germany
            "EWU",   # UK
            "EWY",   # South Korea
            "EWT",   # Taiwan
            "EWZ",   # Brazil
            "EWC",   # Canada
            "EWA",   # Australia
            # Bond ETFs
            "BND",   # Total Bond Market
            "AGG",   # US Aggregate Bond
            "TLT",   # 20+ Year Treasury
            "IEF",   # 7-10 Year Treasury
            "SHY",   # 1-3 Year Treasury
            "LQD",   # Investment Grade Corp
            "HYG",   # High Yield Corp
            "TIP",   # TIPS
            "BNDX",  # International Bond
            "EMB",   # Emerging Market Bond
            # Commodity ETFs
            "GLD",   # Gold
            "SLV",   # Silver
            "IAU",   # Gold Trust
            "USO",   # Oil
            "UNG",   # Natural Gas
            "DBA",   # Agriculture
            "DBC",   # Commodities
            "PDBC",  # Commodities
            "GSG",   # S&P GSCI
            "COMT",  # Commodities
            # Dividend ETFs
            "VYM",   # High Dividend Yield
            "DVY",   # Dividend Select
            "HDV",   # High Dividend
            "SPHD",  # S&P 500 High Div
            "SDY",   # S&P Dividend
            "VIG",   # Dividend Appreciation
            "DGRO",  # Dividend Growth
            "NOBL",  # Dividend Aristocrats
            "SPYD",  # S&P 500 High Div
            "DGRW",  # Dividend Growth
            # Real Estate ETFs
            "VNQ",   # Real Estate
            "IYR",   # US Real Estate
            "SCHH",  # US REIT
            "RWR",   # DJ REIT
            "REET",  # Global REIT
            # Volatility & Hedging
            "VXX",   # VIX Short-Term
            "UVXY",  # VIX 1.5x
            "SVXY",  # Short VIX
            "VIXY",  # VIX
            "TAIL",  # Tail Risk
        ]
    },
    "crypto_etfs": {
        "name": "Crypto & Bitcoin ETFs",
        "type": "etfs",
        "tickers": [
            "IBIT",  # iShares Bitcoin Trust
            "FBTC",  # Fidelity Bitcoin
            "GBTC",  # Grayscale Bitcoin
            "ARKB",  # ARK Bitcoin
            "BITB",  # Bitwise Bitcoin
            "BTCO",  # Invesco Galaxy Bitcoin
            "HODL",  # VanEck Bitcoin
            "BRRR",  # Valkyrie Bitcoin
            "BTCW",  # WisdomTree Bitcoin
            "EZBC",  # Franklin Bitcoin
            "ETHE",  # Grayscale Ethereum
            "BITO",  # ProShares Bitcoin Strategy
            "BTF",   # Valkyrie Bitcoin Strategy
            "XBTF",  # VanEck Bitcoin Strategy
            "BITS",  # Global X Bitcoin Strategy
        ]
    },
    "crypto": {
        "name": "Cryptomonnaies",
        "type": "crypto",
        "tickers": [
            # Top Cryptos
            "BTC-USD",   # Bitcoin
            "ETH-USD",   # Ethereum
            "BNB-USD",   # Binance Coin
            "XRP-USD",   # Ripple
            "SOL-USD",   # Solana
            "ADA-USD",   # Cardano
            "DOGE-USD",  # Dogecoin
            "TRX-USD",   # Tron
            "AVAX-USD",  # Avalanche
            "LINK-USD",  # Chainlink
            "DOT-USD",   # Polkadot
            "MATIC-USD", # Polygon
            "SHIB-USD",  # Shiba Inu
            "LTC-USD",   # Litecoin
            "BCH-USD",   # Bitcoin Cash
            "UNI-USD",   # Uniswap
            "ATOM-USD",  # Cosmos
            "XLM-USD",   # Stellar
            "ETC-USD",   # Ethereum Classic
            "NEAR-USD",  # Near Protocol
            "APT-USD",   # Aptos
            "FIL-USD",   # Filecoin
            "ALGO-USD",  # Algorand
            "VET-USD",   # VeChain
            "HBAR-USD",  # Hedera
            "ICP-USD",   # Internet Computer
            "AAVE-USD",  # Aave
            "MKR-USD",   # Maker
            "GRT-USD",   # The Graph
            "FTM-USD",   # Fantom
            "SAND-USD",  # The Sandbox
            "MANA-USD",  # Decentraland
            "AXS-USD",   # Axie Infinity
            "THETA-USD", # Theta
            "XTZ-USD",   # Tezos
            "EOS-USD",   # EOS
            "EGLD-USD",  # MultiversX
            "FLOW-USD",  # Flow
            "CHZ-USD",   # Chiliz
            "LDO-USD",   # Lido DAO
            "CRV-USD",   # Curve
            "SNX-USD",   # Synthetix
            "COMP-USD",  # Compound
            "RPL-USD",   # Rocket Pool
            "ENS-USD",   # Ethereum Name Service
            "OP-USD",    # Optimism
            "ARB-USD",   # Arbitrum
            "SUI-USD",   # Sui
            "SEI-USD",   # Sei
            "INJ-USD",   # Injective
        ]
    }
}


def get_market_tickers(market: str, limit: int = None) -> list:
    """Get tickers for a specific market with optional limit"""
    market = market.lower()
    if market in MARKETS:
        tickers = MARKETS[market]["tickers"]
        if limit:
            return tickers[:limit]
        return tickers
    return []


def get_all_markets() -> dict:
    """Get all available markets with their full count"""
    return {
        k: {
            "name": v["name"],
            "count": len(v["tickers"])
        }
        for k, v in MARKETS.items()
    }
