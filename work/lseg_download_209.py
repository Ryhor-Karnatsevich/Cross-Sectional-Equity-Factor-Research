"""Run on university PC with LSEG Workspace signed in: python lseg_download_209.py

Requires lseg-data and pandas. Downloads a frozen list of 209 CANDIDATES.
Nothing is merged into the project or declared verified automatically.
"""
import hashlib
import inspect
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import lseg.data as ld


START_DATE = '2008-01-01'
END_DATE = '2026-08-18'
CHUNK_YEARS = 5
PAUSE_SECONDS = 0.3
ATTEMPTS = 2
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / 'lseg_download_209'

# Frozen from single_security_review rows of the user's LSEG mapping export.
# Ticker identities remain candidates even when only one security was found.
EMBEDDED_REQUESTS = r'''
[{"ticker":"AABA","company":"Altaba Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"AABA.O^J19","alternative_rics":"AABA.ARC^J19;AABA.A^J19;AABA.BAT^J19;AABA.BT1^J19;AABA.BYX^J19;AABA.B^J19;AABA.C^J19;AABA.DF^J19;AABA.DG^J19;AABA.DY^J19;AABA.EI^J19;AABA.ITC^J19;AABA.MW^J19;AABA.NB^J19;AABA.N^J19;AABA.OQ^J19;AABA.PH^J19;AABA.P^J19;AABA.ZY^J19;AABA.Z^J19","isin":"US0213461017","requested_start":"2008-01-02","requested_end":"2017-06-16"},
{"ticker":"ABI","company":"Applied Biosystems Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"ABI.N^K08","alternative_rics":"ABI.C^K08;ABI.DF^K08;ABI.II^K08;ABI.MW^K08;ABI.PH^K08;ABI.P^K08;ABI.TH^K08;ABI.W^K08;ABI.Z^K08;ABI^K08","isin":"US0381491002","requested_start":"2008-01-02","requested_end":"2008-11-21"},
{"ticker":"ABKFQ","company":"Ambac Financial Group Ord Shs, Ordinary Share, Delisted, OTC MARKETS GROUP L1 AND L2","ric":"ABKFQ.PK^E13","alternative_rics":"","isin":"US0231391089","requested_start":"2008-01-02","requested_end":"2008-06-10"},
{"ticker":"ABMD","company":"ABIOMED Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"ABMD.O^L22","alternative_rics":"ABMD.AOI^L22;ABMD.ARC^L22;ABMD.A^L22;ABMD.BAT^L22;ABMD.BT1^L22;ABMD.BYX^L22;ABMD.B^L22;ABMD.C^L22;ABMD.DF^L22;ABMD.DG^L22;ABMD.DY^L22;ABMD.EI^L22;ABMD.ITC^L22;ABMD.LTS^L22;ABMD.MEM^L22;ABMD.MP^L22;ABMD.MW^L22;ABMD.NB^L22;ABMD.NOI^L22;ABMD.NQT^L22;ABMD.N^L22;ABMD.OQ^L22;ABMD.PH^L22;ABMD.P^L22;ABMD.ZY^L22;ABMD.Z^L22","isin":"US0036541003","requested_start":"2018-05-31","requested_end":"2022-12-21"},
{"ticker":"ACAS","company":"American Capital Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"ACAS.O^A17","alternative_rics":"ACAS.A^J16;ACAS.BAT^A17;ACAS.BYX^A17;ACAS.B^A17;ACAS.C^A17;ACAS.DF^A17;ACAS.DG^A17;ACAS.DY^A17;ACAS.EI^A17;ACAS.II^G10;ACAS.ITC^A17;ACAS.MW^A17;ACAS.NB^A17;ACAS.OQ^A17;ACAS.PH^A17;ACAS.PH^B09;ACAS.P^A17;ACAS.W^E14;ACAS.ZY^A17;ACAS.Z^A17","isin":"US02503Y1038","requested_start":"2008-01-02","requested_end":"2009-03-03"},
{"ticker":"ACS","company":"Affiliated Computer Services Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"ACS^B10","alternative_rics":"ACS.B^B10;ACS.C^B10;ACS.DF^B10;ACS.II^B10;ACS.MW^B10;ACS.N^B10;ACS.PH^B09;ACS.P^B10;ACS.TH^B10;ACS.W^B10;ACS.Z^B10","isin":"US0081901003","requested_start":"2008-01-02","requested_end":"2010-02-05"},
{"ticker":"AKS","company":"AK Steel Holding Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"AKS^C20","alternative_rics":"AKS.ARC^C20;AKS.A^C20;AKS.BAT^C20;AKS.BT1^C20;AKS.BYX^C20;AKS.B^C20;AKS.C^C20;AKS.DF^C20;AKS.DG^C20;AKS.DY^C20;AKS.EI^C20;AKS.II^G10;AKS.ITC^C20;AKS.MW^C20;AKS.NB^C20;AKS.N^C20;AKS.PH^B09;AKS.PH^C20;AKS.P^C20;AKS.TH^C20;AKS.W^E14;AKS.ZY^C20;AKS.Z^C20","isin":"US0015471081","requested_start":"2008-07-01","requested_end":"2011-12-16"},
{"ticker":"ALXN","company":"Alexion Pharmaceuticals Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"ALXN.O^G21","alternative_rics":"ALXN.ARC^G21;ALXN.A^G21;ALXN.BAT^G21;ALXN.BT1^G21;ALXN.BYX^G21;ALXN.B^G21;ALXN.C^G21;ALXN.DF^G21;ALXN.DG^G21;ALXN.DY^G21;ALXN.EI^G21;ALXN.ITC^G21;ALXN.LTS^G21;ALXN.MEM^G21;ALXN.MP^G21;ALXN.MW^G21;ALXN.NB^G21;ALXN.N^G21;ALXN.OQ^G21;ALXN.PH^G21;ALXN.P^G21;ALXN.W^E14;ALXN.ZY^G21;ALXN.Z^G21","isin":"US0153511094","requested_start":"2012-05-25","requested_end":"2021-07-20"},
{"ticker":"ANRZQ","company":"Alpha Natural Resources Ord Shs, Ordinary Share, Delisted, OTC MARKETS GROUP L1 AND L2","ric":"ANRZQ.PK^G16","alternative_rics":"ANRZQ.PQ^G16","isin":"US02076X1028","requested_start":"2011-06-02","requested_end":"2012-10-01"},
{"ticker":"ANSS","company":"ANSYS Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"ANSS.O^G25","alternative_rics":"ANSS.AOI^G25;ANSS.ARC^G25;ANSS.A^G25;ANSS.BAT^G25;ANSS.BLUE^G25;ANSS.BT1^G25;ANSS.BYX^G25;ANSS.B^G25;ANSS.C^G25;ANSS.DEX^G25;ANSS.DF^G25;ANSS.DG^G25;ANSS.DY^G25;ANSS.EI^G25;ANSS.ITC^G25;ANSS.LTS^G25;ANSS.MEM^G25;ANSS.MP^G25;ANSS.MW^G25;ANSS.NB^G25;ANSS.NOI^G25;ANSS.NQT^G25;ANSS.N^G25;ANSS.OQ^G25;ANSS.PH^G25;ANSS.P^G25;ANSS.ZY^G25;ANSS.Z^G25","isin":"US03662Q1058","requested_start":"2017-06-19","requested_end":"2025-07-17"},
{"ticker":"APOL","company":"Apollo Education Group Ord Shs Class A, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"APOL.O^B17","alternative_rics":"APOL.A^C12;APOL.A^H14;APOL.BAT^B17;APOL.BYX^B17;APOL.B^B17;APOL.C^B17;APOL.DF^B17;APOL.DG^B17;APOL.DY^B17;APOL.EI^B17;APOL.II^G10;APOL.ITC^B17;APOL.MW^B17;APOL.NB^B17;APOL.OQ^B17;APOL.PH^B09;APOL.PH^B17;APOL.P^B17;APOL.W^E14;APOL.ZY^B17;APOL.Z^B17","isin":"US0376041051","requested_start":"2008-01-02","requested_end":"2013-06-28"},
{"ticker":"ARG","company":"Airgas Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"ARG^E16","alternative_rics":"ARG.BAT^E16;ARG.BYX^E16;ARG.B^E16;ARG.C^E16;ARG.DF^E16;ARG.DG^E16;ARG.DY^E16;ARG.II^G10;ARG.ITC^E16;ARG.MW^E16;ARG.NB^E16;ARG.N^E16;ARG.PH^E16;ARG.P^E16;ARG.TH^E16;ARG.W^E14;ARG.ZY^E16;ARG.Z^E16","isin":"US0093631028","requested_start":"2009-09-09","requested_end":"2016-05-20"},
{"ticker":"ARNC","company":"Arconic Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"ARNC.K^H23","alternative_rics":"ARNC.AOI^H23;ARNC.ARC^H23;ARNC.A^H23;ARNC.BAT^H23;ARNC.BT1^H23;ARNC.BYX^H23;ARNC.B^H23;ARNC.C^H23;ARNC.DF^H23;ARNC.DG^H23;ARNC.DY^H23;ARNC.EI^H23;ARNC.ITC^H23;ARNC.LTS^H23;ARNC.MEM^H23;ARNC.MP^H23;ARNC.MW^H23;ARNC.NB^H23;ARNC.NOI^H23;ARNC.NQT^H23;ARNC.N^H23;ARNC.PH^H23;ARNC.P^H23;ARNC.TH^H23;ARNC.ZY^H23;ARNC.Z^H23","isin":"US03966V1070","requested_start":"2008-01-02","requested_end":"2020-04-03"},
{"ticker":"ATVI","company":"Activision Blizzard Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"ATVI.O^J23","alternative_rics":"ATVI.AOI^J23;ATVI.ARC^J23;ATVI.A^J23;ATVI.BAT^J23;ATVI.BT1^J23;ATVI.BYX^J23;ATVI.B^J23;ATVI.C^J23;ATVI.DEX^J23;ATVI.DF^J23;ATVI.DG^J23;ATVI.DY^J23;ATVI.EI^J23;ATVI.ITC^J23;ATVI.LTS^J23;ATVI.MEM^J23;ATVI.MP^J23;ATVI.MW^J23;ATVI.NB^J23;ATVI.NOI^J23;ATVI.NQT^J23;ATVI.N^J23;ATVI.OQ^J23;ATVI.PH^J23;ATVI.P^J23;ATVI.ZY^J23;ATVI.Z^J23","isin":"US00507V1098","requested_start":"2015-08-31","requested_end":"2023-10-17"},
{"ticker":"AVB","company":"AvalonBay Communities REIT Ord Shs, Ordinary Share, Delisted, NYSE AMEX IMBALANCE","ric":"AVB.AOI^H26","alternative_rics":"AVB.ARC^H26;AVB.A^H26;AVB.BAT^H26;AVB.BLUE^H26;AVB.BT1^H26;AVB.BYX^H26;AVB.B^H26;AVB.C^H26;AVB.DEX^H26;AVB.DF^H26;AVB.DG^H26;AVB.DY^H26;AVB.EI^H26;AVB.II^G10;AVB.ITC^H26;AVB.LTS^H26;AVB.MEM^H26;AVB.MP^H26;AVB.NB^H26;AVB.NIB^H26;AVB.NOI^H26;AVB.NQT^H26;AVB.N^H26;AVB.PH^B09;AVB.PH^H26;AVB.P^H26;AVB.TXS^H26;AVB.W^E14;AVB.XN^H26;AVB.ZY^H26;AVB.Z^H26;AVB^H26","isin":"US0534841012","requested_start":"2008-01-02","requested_end":"2026-08-17"},
{"ticker":"AVP","company":"Avon Products Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"AVP^A20","alternative_rics":"AVP.ARC^A20;AVP.A^A20;AVP.BAT^A20;AVP.BT1^A20;AVP.BYX^A20;AVP.B^A20;AVP.C^A20;AVP.DF^A20;AVP.DG^A20;AVP.DY^A20;AVP.EI^A20;AVP.II^G10;AVP.ITC^A20;AVP.MW^A20;AVP.NB^A20;AVP.N^A20;AVP.PH^A20;AVP.PH^B09;AVP.P^A20;AVP.TH^A20;AVP.W^E14;AVP.ZY^A20;AVP.Z^A20","isin":"US0543031027","requested_start":"2008-01-02","requested_end":"2015-03-20"},
{"ticker":"AYE","company":"Allegheny Energy Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"AYE^B11","alternative_rics":"AYE.B^B11;AYE.C^B11;AYE.DF^B11;AYE.DG^B11;AYE.DY^B11;AYE.II^G10;AYE.MW^B11;AYE.N^B11;AYE.PH^B09;AYE.PH^B11;AYE.P^B11;AYE.TH^B11;AYE.W^B11;AYE.ZY^B11;AYE.Z^B11","isin":"US0173611064","requested_start":"2008-01-02","requested_end":"2011-02-25"},
{"ticker":"BCR","company":"C R Bard Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"BCR^L17","alternative_rics":"BCR.A^L17;BCR.BAT^L17;BCR.BT1^L17;BCR.BYX^L17;BCR.B^L17;BCR.C^L17;BCR.DF^L17;BCR.DG^L17;BCR.DY^L17;BCR.EI^L17;BCR.II^G10;BCR.ITC^L17;BCR.MW^L17;BCR.NB^L17;BCR.N^L17;BCR.PH^B09;BCR.PH^L17;BCR.P^L17;BCR.TH^L17;BCR.W^E14;BCR.ZY^L17;BCR.Z^L17","isin":"US0673831097","requested_start":"2008-01-02","requested_end":"2017-12-28"},
{"ticker":"BDK","company":"Black & Decker Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"BDK.N^C10","alternative_rics":"BDK.B^C10;BDK.C^C10;BDK.DF^C10;BDK.II^C10;BDK.MW^C10;BDK.PH^B09;BDK.P^C10;BDK.TH^C10;BDK.W^C10;BDK.Z^C10;BDK^C10","isin":"US0917971006","requested_start":"2008-01-02","requested_end":"2010-03-12"},
{"ticker":"BIG","company":"Big Lots Ord Shs, Ordinary Share, Delisted, NYSE AMEX IMBALANCE","ric":"BIG.AOI^I24","alternative_rics":"BIG.ARC^I24;BIG.A^I24;BIG.BAT^I24;BIG.BT1^I24;BIG.BYX^I24;BIG.B^I24;BIG.C^I24;BIG.DEX^I24;BIG.DF^I24;BIG.DG^I24;BIG.DY^I24;BIG.EI^I24;BIG.II^G10;BIG.ITC^I24;BIG.LTS^I24;BIG.MEM^I24;BIG.MP^I24;BIG.MW^I24;BIG.NB^I24;BIG.NOI^I24;BIG.NQT^I24;BIG.N^I24;BIG.PH^B09;BIG.PH^I24;BIG.P^I24;BIG.TH^I24;BIG.W^E14;BIG.ZY^I24;BIG.Z^I24","isin":"US0893021032","requested_start":"2008-01-02","requested_end":"2013-02-13"},
{"ticker":"BJS","company":"BJ Services Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"BJS^D10","alternative_rics":"BJS.B^D10;BJS.C^D10;BJS.DF^D10;BJS.II^D10;BJS.MW^D10;BJS.N^D10;BJS.PH^B09;BJS.P^D10;BJS.TH^D10;BJS.W^D10;BJS.Z^D10","isin":"US0554821035","requested_start":"2008-01-02","requested_end":"2010-04-28"},
{"ticker":"BK","company":"Bank of New York Mellon Ord Shs, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"BK.II^G10","alternative_rics":"BK.PH^B09;BK.W^E14","isin":"US0640581007","requested_start":"2008-01-02","requested_end":"2026-05-20"},
{"ticker":"BMC","company":"BMC Software Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"BMC.O^I13","alternative_rics":"BMC.A^B12;BMC.B^I13;BMC.C^I13;BMC.DF^I13;BMC.DG^I13;BMC.DY^I13;BMC.II^G10;BMC.MW^I13;BMC.NB^I13;BMC.OQ^I13;BMC.PH^B09;BMC.PH^I13;BMC.P^I13;BMC.TH^J09;BMC.W^I13;BMC.ZY^I13;BMC.Z^I13","isin":"US0559211000","requested_start":"2008-01-02","requested_end":"2013-09-10"},
{"ticker":"BNI","company":"Burlington Northern Santa Fe Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"BNI.N^B10","alternative_rics":"BNI.B^B10;BNI.C^B10;BNI.DF^B10;BNI.II^B10;BNI.MW^B10;BNI.PH^B09;BNI.P^B10;BNI.TH^B10;BNI.W^B10;BNI.Z^B10;BNI^B10","isin":"US12189T1043","requested_start":"2008-01-02","requested_end":"2010-02-12"},
{"ticker":"BRCM","company":"Broadcom Ord Shs Class A, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"BRCM.O^B16","alternative_rics":"BRCM.A^B12;BRCM.A^B16;BRCM.BAT^B16;BRCM.BYX^B16;BRCM.B^B16;BRCM.C^B16;BRCM.DF^B16;BRCM.DG^B16;BRCM.DY^B16;BRCM.II^G10;BRCM.ITC^B16;BRCM.MW^B16;BRCM.NB^B16;BRCM.OQ^B16;BRCM.PH^B09;BRCM.PH^B16;BRCM.P^B16;BRCM.W^E14;BRCM.ZY^B16;BRCM.Z^B16","isin":"US1113201073","requested_start":"2008-01-02","requested_end":"2016-01-29"},
{"ticker":"BRL","company":"Barr Pharmaceuticals Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"BRL.N^L08","alternative_rics":"BRL.C^L08;BRL.DF^L08;BRL.II^L08;BRL.MW^L08;BRL.PH^L08;BRL.P^L08;BRL.TH^L08;BRL.W^L08;BRL.Z^L08;BRL^L08","isin":"US0683061099","requested_start":"2008-01-02","requested_end":"2008-12-22"},
{"ticker":"BSC","company":"Bear Stearns Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"BSC.N^F08","alternative_rics":"BSC.C^F08;BSC.DF^F08;BSC.II^F08;BSC.MW^F08;BSC.PH^F08;BSC.P^F08;BSC.TH^F08;BSC.W^F08;BSC^F08","isin":"US0739021089","requested_start":"2008-01-02","requested_end":"2008-05-30"},
{"ticker":"BTUUQ","company":"Peabody Energy Ord Shs, Ordinary Share, Delisted, OTC MARKETS GROUP L1 AND L2","ric":"BTUUQ.PK^D17","alternative_rics":"BTUUQ.PQ^D17","isin":"US7045492037","requested_start":"2008-01-02","requested_end":"2014-09-19"},
{"ticker":"BXLT","company":"Baxalta Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"BXLT.K^F16","alternative_rics":"BXLT.BAT^F16;BXLT.BYX^F16;BXLT.B^F16;BXLT.C^F16;BXLT.DF^F16;BXLT.DG^F16;BXLT.DY^F16;BXLT.ITC^F16;BXLT.MW^F16;BXLT.NB^F16;BXLT.N^F16;BXLT.PH^F16;BXLT.P^F16;BXLT.TH^F16;BXLT.ZY^F16;BXLT.Z^F16","isin":"US07177M1036","requested_start":"2015-07-01","requested_end":"2016-06-02"},
{"ticker":"CA","company":"CA Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"CA.O^K18","alternative_rics":"CA.A^K18;CA.BAT^K18;CA.BT1^K18;CA.BYX^K18;CA.B^K18;CA.C^K18;CA.DF^K18;CA.DG^K18;CA.DY^K18;CA.EI^K18;CA.II^G10;CA.ITC^K18;CA.MW^K18;CA.NB^K18;CA.N^K18;CA.OQ^K18;CA.PH^B09;CA.PH^K18;CA.P^K18;CA.TH^D08;CA.W^E14;CA.ZY^K18;CA.Z^K18","isin":"US12673P1057","requested_start":"2008-01-02","requested_end":"2018-11-05"},
{"ticker":"CAM","company":"Cameron International Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"CAM^D16","alternative_rics":"CAM.BAT^D16;CAM.BYX^D16;CAM.B^D16;CAM.C^D16;CAM.DF^D16;CAM.DG^D16;CAM.DY^D16;CAM.II^G10;CAM.ITC^D16;CAM.MW^D16;CAM.NB^D16;CAM.N^D16;CAM.PH^B09;CAM.PH^D16;CAM.P^D16;CAM.TH^D16;CAM.W^E14;CAM.ZY^D16;CAM.Z^D16","isin":"US13342B1052","requested_start":"2008-01-29","requested_end":"2016-04-01"},
{"ticker":"CBE","company":"Cooper Industries Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"CBE^L12","alternative_rics":"CBE.B^L12;CBE.C^L12;CBE.DF^L12;CBE.DG^L12;CBE.DY^L12;CBE.II^G10;CBE.MW^L12;CBE.N^L12;CBE.PH^B09;CBE.PH^L12;CBE.P^L12;CBE.TH^L12;CBE.W^L12;CBE.ZY^L12;CBE.Z^L12","isin":"IE00B40K9117","requested_start":"2008-01-02","requested_end":"2012-11-30"},
{"ticker":"CBH","company":"Commerce Bancorp Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"CBH.N^D08","alternative_rics":"CBH.C^D08;CBH.DF^D08;CBH.II^D08;CBH.MW^D08;CBH.PH^D08;CBH.P^D08;CBH.TH^D08;CBH.W^D08;CBH^D08","isin":"US2005191067","requested_start":"2008-01-02","requested_end":"2008-03-28"},
{"ticker":"CBS","company":"Skydance Ord shs Class B, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"CBS.II^G10","alternative_rics":"CBS.PH^B09;CBS.TH^L19;CBS.W^E14","isin":"US69932A2042","requested_start":"2008-01-02","requested_end":"2019-12-04"},
{"ticker":"CCE","company":"Coca Cola Europacific Partners Ord Shs, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"CCE.II^G10","alternative_rics":"CCE.PH^B09;CCE.W^E14","isin":"GB00BDCPN049","requested_start":"2008-01-02","requested_end":"2016-05-27"},
{"ticker":"CCTYQ","company":"Circuit City Stores Ord Shs, Ordinary Share, Delisted, OTC Markets Group Inc - No Information","ric":"CCTYQ.PK^I11","alternative_rics":"","isin":"US1727371080","requested_start":"2008-01-02","requested_end":"2008-03-28"},
{"ticker":"CELG","company":"Celgene Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"CELG.O^K19","alternative_rics":"CELG.ARC^K19;CELG.A^C12;CELG.A^K19;CELG.BAT^K19;CELG.BT1^K19;CELG.BYX^K19;CELG.B^K19;CELG.C^K19;CELG.DF^K19;CELG.DG^K19;CELG.DY^K19;CELG.EI^K19;CELG.II^G10;CELG.ITC^K19;CELG.MW^K19;CELG.NB^K19;CELG.N^K19;CELG.OQ^K19;CELG.PH^B09;CELG.PH^K19;CELG.P^K19;CELG.W^E14;CELG.ZY^K19;CELG.Z^K19","isin":"US1510201049","requested_start":"2008-01-02","requested_end":"2019-11-20"},
{"ticker":"CEPH","company":"Cephalon Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"CEPH.O^J11","alternative_rics":"CEPH.A^J11;CEPH.B^J11;CEPH.C^J11;CEPH.DF^J11;CEPH.DG^J11;CEPH.DY^J11;CEPH.II^G10;CEPH.MW^J11;CEPH.OQ^J11;CEPH.PH^B09;CEPH.PH^J11;CEPH.P^J11;CEPH.W^J11;CEPH.ZY^J11;CEPH.Z^J11","isin":"US1567081096","requested_start":"2008-11-17","requested_end":"2011-10-13"},
{"ticker":"CERN","company":"Cerner Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"CERN.O^F22","alternative_rics":"CERN.ARC^F22;CERN.A^C12;CERN.A^F22;CERN.BAT^F22;CERN.BT1^F22;CERN.BYX^F22;CERN.B^F22;CERN.C^F22;CERN.DF^F22;CERN.DG^F22;CERN.DY^F22;CERN.EI^F22;CERN.II^G10;CERN.ITC^F22;CERN.LTS^F22;CERN.MEM^F22;CERN.MP^F22;CERN.MW^F22;CERN.NB^F22;CERN.NQT^F22;CERN.N^F22;CERN.OQ^F22;CERN.PH^F22;CERN.P^F22;CERN.W^E14;CERN.ZY^F22;CERN.Z^F22","isin":"US1567821046","requested_start":"2010-04-30","requested_end":"2022-06-07"},
{"ticker":"CFC","company":"Countrywide Financial Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"CFC.N^G08","alternative_rics":"CFC.C^G08;CFC.DF^G08;CFC.II^G08;CFC.MW^G08;CFC.PH^G08;CFC.P^G08;CFC.TH^G08;CFC.W^G08;CFC^G08","isin":"US2223721042","requested_start":"2008-01-02","requested_end":"2008-06-30"},
{"ticker":"CFN","company":"CareFusion Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"CFN^C15","alternative_rics":"CFN.BAT^C15;CFN.BYX^C15;CFN.B^C15;CFN.C^G14;CFN.DF^C15;CFN.DG^C15;CFN.DY^C15;CFN.II^G10;CFN.ITC^C15;CFN.MW^C15;CFN.NB^C15;CFN.N^C15;CFN.PH^C15;CFN.P^C15;CFN.TH^C15;CFN.W^E14;CFN.ZY^C15;CFN.Z^C15","isin":"US14170T1016","requested_start":"2009-09-01","requested_end":"2015-03-16"},
{"ticker":"CHK","company":"Chesapeake Energy Ord Shs, Ordinary Share, Delisted, NYSE ArcaBook Equities","ric":"CHK.ARC^F20","alternative_rics":"CHK.A^F20;CHK.BAT^F20;CHK.BT1^F20;CHK.BYX^F20;CHK.B^F20;CHK.C^F20;CHK.DF^F20;CHK.DG^F20;CHK.DY^F20;CHK.EI^F20;CHK.II^G10;CHK.ITC^F20;CHK.MW^F20;CHK.NB^F20;CHK.N^F20;CHK.PH^B09;CHK.PH^F20;CHK.P^F20;CHK.TH^F20;CHK.W^E14;CHK.ZY^F20;CHK.Z^F20","isin":"US1651677437","requested_start":"2008-01-02","requested_end":"2018-03-16"},
{"ticker":"CITGQ","company":"CIT Group Ord Shs, Ordinary Share, Delisted, US 'Other OTC' and Grey Market","ric":"CITGQ.PK^L09","alternative_rics":"","isin":"US1255811085","requested_start":"2008-01-02","requested_end":"2009-07-24"},
{"ticker":"CMA","company":"Comerica Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"CMA^B26","alternative_rics":"CMA.AOI^B26;CMA.ARC^B26;CMA.A^B26;CMA.BAT^B26;CMA.BLUE^B26;CMA.BT1^B26;CMA.BYX^B26;CMA.B^B26;CMA.C^B26;CMA.DEX^B26;CMA.DF^B26;CMA.DG^B26;CMA.DY^B26;CMA.EI^B26;CMA.II^G10;CMA.ITC^B26;CMA.LTS^B26;CMA.MEM^B26;CMA.MP^B26;CMA.MW^B26;CMA.NB^B26;CMA.NOI^B26;CMA.NQT^B26;CMA.N^B26;CMA.PH^B09;CMA.PH^B26;CMA.P^B26;CMA.TH^B26;CMA.W^E14;CMA.XN^B26;CMA.ZY^B26;CMA.Z^B26","isin":"US2003401070","requested_start":"2008-01-02","requested_end":"2024-06-21"},
{"ticker":"CMCSK","company":"Comcast Special Ord Shs Class A, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"CMCSK.O^L15","alternative_rics":"CMCSK.BAT^L15;CMCSK.BYX^L15;CMCSK.B^L15;CMCSK.DF^L15;CMCSK.DG^L15;CMCSK.DY^L15;CMCSK.ITC^L15;CMCSK.MW^L15;CMCSK.NB^L15;CMCSK.OQ^L15;CMCSK.PH^L15;CMCSK.P^L15;CMCSK.ZY^L15;CMCSK.Z^L15","isin":"US20030N2009","requested_start":"2015-09-21","requested_end":"2015-12-11"},
{"ticker":"COG","company":"Coterra Energy Ord Shs, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"COG.II^G10","alternative_rics":"COG.PH^B09;COG.W^E14","isin":"US1270971039","requested_start":"2008-06-23","requested_end":"2021-10-01"},
{"ticker":"COL","company":"Rockwell Collins Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"COL^K18","alternative_rics":"COL.ARC^K18;COL.A^K18;COL.BAT^K18;COL.BT1^K18;COL.BYX^K18;COL.B^K18;COL.C^K18;COL.DF^K18;COL.DG^K18;COL.DY^K18;COL.EI^K18;COL.II^G10;COL.ITC^K18;COL.MW^K18;COL.NB^K18;COL.N^K18;COL.PH^B09;COL.PH^K18;COL.P^K18;COL.TH^K18;COL.W^E14;COL.ZY^K18;COL.Z^K18","isin":"US7743411016","requested_start":"2008-01-02","requested_end":"2018-11-26"},
{"ticker":"COV","company":"Covidien Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"COV^A15","alternative_rics":"COV.BAT^A15;COV.BYX^A15;COV.B^A15;COV.C^G14;COV.DF^A15;COV.DG^A15;COV.DY^A15;COV.II^G10;COV.ITC^A15;COV.MW^A15;COV.NB^A15;COV.N^A15;COV.PH^A15;COV.PH^B09;COV.P^A15;COV.TH^A15;COV.W^E14;COV.ZY^A15;COV.Z^A15","isin":"IE00B68SQD29","requested_start":"2008-01-02","requested_end":"2015-01-26"},
{"ticker":"CPGX","company":"Columbia Pipeline Group Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"CPGX.K^G16","alternative_rics":"CPGX.BAT^G16;CPGX.BYX^G16;CPGX.B^G16;CPGX.C^G16;CPGX.DF^G16;CPGX.DG^G16;CPGX.DY^G16;CPGX.ITC^G16;CPGX.MW^G16;CPGX.NB^G16;CPGX.N^G16;CPGX.PH^G16;CPGX.P^G16;CPGX.TH^G16;CPGX.ZY^G16;CPGX.Z^G16","isin":"US1982801094","requested_start":"2015-07-02","requested_end":"2016-06-30"},
{"ticker":"CSRA","company":"CSRA Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"CSRA.K^D18","alternative_rics":"CSRA.A^D18;CSRA.BAT^D18;CSRA.BT1^D18;CSRA.BYX^D18;CSRA.B^D18;CSRA.C^D18;CSRA.DF^D18;CSRA.DG^D18;CSRA.DY^D18;CSRA.EI^D18;CSRA.ITC^D18;CSRA.MW^D18;CSRA.NB^D18;CSRA.N^D18;CSRA.PH^D18;CSRA.P^D18;CSRA.TH^D18;CSRA.ZY^D18;CSRA.Z^D18","isin":"US12650T1043","requested_start":"2015-11-30","requested_end":"2018-04-03"},
{"ticker":"CTLT","company":"Catalent  Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"CTLT.K^L24","alternative_rics":"CTLT.AOI^L24;CTLT.ARC^L24;CTLT.A^L24;CTLT.BAT^L24;CTLT.BT1^L24;CTLT.BYX^L24;CTLT.B^L24;CTLT.C^L24;CTLT.DEX^L24;CTLT.DF^L24;CTLT.DG^L24;CTLT.DY^L24;CTLT.EI^L24;CTLT.ITC^L24;CTLT.LTS^L24;CTLT.MEM^L24;CTLT.MP^L24;CTLT.MW^L24;CTLT.NB^L24;CTLT.NOI^L24;CTLT.NQT^L24;CTLT.N^L24;CTLT.PH^L24;CTLT.P^L24;CTLT.TH^L24;CTLT.ZY^L24;CTLT.Z^L24","isin":"US1488061029","requested_start":"2020-09-21","requested_end":"2024-12-20"},
{"ticker":"CTRA","company":"Coterra Energy Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"CTRA.K^E26","alternative_rics":"CTRA.AOI^E26;CTRA.ARC^E26;CTRA.A^E26;CTRA.BAT^E26;CTRA.BLUE^E26;CTRA.BT1^E26;CTRA.BYX^E26;CTRA.B^E26;CTRA.C^E26;CTRA.DEX^E26;CTRA.DF^E26;CTRA.DG^E26;CTRA.DY^E26;CTRA.EI^E26;CTRA.ITC^E26;CTRA.LTS^E26;CTRA.MEM^E26;CTRA.MP^E26;CTRA.MW^E26;CTRA.NB^E26;CTRA.NOI^E26;CTRA.NQT^E26;CTRA.N^E26;CTRA.PH^E26;CTRA.P^E26;CTRA.TH^E26;CTRA.XN^E26;CTRA.ZY^E26;CTRA.Z^E26","isin":"US1270971039","requested_start":"2021-10-04","requested_end":"2026-05-06"},
{"ticker":"CTX","company":"Centex Corp Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"CTX.N^H09","alternative_rics":"CTX.B^H09;CTX.C^H09;CTX.DF^H09;CTX.II^H09;CTX.MW^H09;CTX.PH^B09;CTX.P^H09;CTX.TH^H09;CTX.W^H09;CTX.Z^H09;CTX^H09","isin":"US1523121044","requested_start":"2008-01-02","requested_end":"2009-08-18"},
{"ticker":"CTXS","company":"Citrix Systems Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"CTXS.O^J22","alternative_rics":"CTXS.AOI^J22;CTXS.ARC^J22;CTXS.A^I12;CTXS.A^J22;CTXS.BAT^J22;CTXS.BT1^J22;CTXS.BYX^J22;CTXS.B^J22;CTXS.C^J22;CTXS.DF^J22;CTXS.DG^J22;CTXS.DY^J22;CTXS.EI^J22;CTXS.II^G10;CTXS.ITC^J22;CTXS.LTS^J22;CTXS.MEM^J22;CTXS.MP^J22;CTXS.MW^J22;CTXS.NB^J22;CTXS.NOI^J22;CTXS.NQT^J22;CTXS.N^J22;CTXS.OQ^J22;CTXS.PH^B09;CTXS.PH^J22;CTXS.P^J22;CTXS.W^E14;CTXS.ZY^J22;CTXS.Z^J22","isin":"US1773761002","requested_start":"2008-01-02","requested_end":"2022-09-30"},
{"ticker":"CVC","company":"Cablevision Systems Ord Shs Class A, Ordinary Share, Delisted, NYSE Consolidated","ric":"CVC^F16","alternative_rics":"CVC.BAT^F16;CVC.BYX^F16;CVC.B^F16;CVC.C^F16;CVC.DF^F16;CVC.DG^F16;CVC.DY^F16;CVC.ITC^F16;CVC.MW^F16;CVC.NB^F16;CVC.N^F16;CVC.PH^F16;CVC.P^F16;CVC.TH^F16;CVC.W^E14;CVC.ZY^F16;CVC.Z^F16","isin":"US12686C1099","requested_start":"2010-12-20","requested_end":"2016-06-20"},
{"ticker":"CVG","company":"Convergys Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"CVG^J18","alternative_rics":"CVG.A^J18;CVG.BAT^J18;CVG.BT1^J18;CVG.BYX^J18;CVG.B^J18;CVG.C^J18;CVG.DF^J18;CVG.DG^J18;CVG.DY^J18;CVG.EI^J18;CVG.II^G10;CVG.ITC^J18;CVG.MW^J18;CVG.NB^J18;CVG.N^J18;CVG.PH^B09;CVG.PH^J18;CVG.P^J18;CVG.TH^J18;CVG.W^E14;CVG.ZY^J18;CVG.Z^J18","isin":"US2124851062","requested_start":"2008-01-02","requested_end":"2009-12-18"},
{"ticker":"CVH","company":"Coventry Health Care Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"CVH.N^E13","alternative_rics":"CVH.B^E13;CVH.C^E13;CVH.DF^E13;CVH.DG^E13;CVH.DY^E13;CVH.II^G10;CVH.MW^E13;CVH.NB^E13;CVH.PH^B09;CVH.PH^E13;CVH.P^E13;CVH.TH^E13;CVH.W^E13;CVH.ZY^E13;CVH.Z^E13;CVH^E13","isin":"US2228621049","requested_start":"2008-01-02","requested_end":"2013-05-06"},
{"ticker":"CXO","company":"Concho Resources Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"CXO^A21","alternative_rics":"CXO.ARC^A21;CXO.A^A21;CXO.BAT^A21;CXO.BT1^A21;CXO.BYX^A21;CXO.B^A21;CXO.C^A21;CXO.DF^A21;CXO.DG^A21;CXO.DY^A21;CXO.EI^A21;CXO.ITC^A21;CXO.LTS^A21;CXO.MEM^A21;CXO.MP^A21;CXO.MW^A21;CXO.NB^A21;CXO.N^A21;CXO.PH^A21;CXO.P^A21;CXO.TH^A21;CXO.ZY^A21;CXO.Z^A21","isin":"US20605P1012","requested_start":"2016-02-22","requested_end":"2021-01-20"},
{"ticker":"DAY","company":"Dayforce Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"DAY^B26","alternative_rics":"DAY.AOI^B26;DAY.ARC^B26;DAY.A^B26;DAY.BAT^B26;DAY.BLUE^B26;DAY.BT1^B26;DAY.BYX^B26;DAY.B^B26;DAY.C^B26;DAY.DEX^B26;DAY.DF^B26;DAY.DG^B26;DAY.DY^B26;DAY.EI^B26;DAY.ITC^B26;DAY.LTS^B26;DAY.MEM^B26;DAY.MP^B26;DAY.MW^B26;DAY.NB^B26;DAY.NOI^B26;DAY.NQT^B26;DAY.N^B26;DAY.PH^B26;DAY.P^B26;DAY.TH^B26;DAY.XN^B26;DAY.ZY^B26;DAY.Z^B26","isin":"US15677J1088","requested_start":"2024-02-01","requested_end":"2026-02-06"},
{"ticker":"DF","company":"Dean Foods Ord Shs, Ordinary Share, Delisted, NYSE ArcaBook Equities","ric":"DF.ARC^K19","alternative_rics":"DF.A^K19;DF.BAT^K19;DF.BT1^K19;DF.BYX^K19;DF.B^K19;DF.C^K19;DF.DF^K19;DF.DG^K19;DF.DY^K19;DF.EI^K19;DF.II^G10;DF.ITC^K19;DF.MW^K19;DF.NB^K19;DF.N^K19;DF.PH^B09;DF.PH^K19;DF.P^K19;DF.TH^K19;DF.W^E14;DF.ZY^K19;DF.Z^K19","isin":"US2423702032","requested_start":"2008-01-02","requested_end":"2013-05-23"},
{"ticker":"DFS","company":"Discover Financial Services Ord Shs, Ordinary Share, Delisted, NYSE AMEX IMBALANCE","ric":"DFS.AOI^E25","alternative_rics":"DFS.ARC^E25;DFS.A^E25;DFS.BAT^E25;DFS.BLUE^E25;DFS.BT1^E25;DFS.BYX^E25;DFS.B^E25;DFS.C^E25;DFS.DEX^E25;DFS.DF^E25;DFS.DG^E25;DFS.DY^E25;DFS.EI^E25;DFS.II^G10;DFS.ITC^E25;DFS.LTS^E25;DFS.MEM^E25;DFS.MP^E25;DFS.MW^E25;DFS.NB^E25;DFS.NOI^E25;DFS.NQT^E25;DFS.N^E25;DFS.PH^B09;DFS.PH^E25;DFS.P^E25;DFS.TH^E25;DFS.W^E14;DFS.ZY^E25;DFS.Z^E25;DFS^E25","isin":"US2547091080","requested_start":"2008-01-02","requested_end":"2025-05-16"},
{"ticker":"DISCA","company":"Warner Bros. Discovery Ord Shs Series A, Ordinary Share, Delisted, NYSE American when trading NASDAQ Global Select Mkt","ric":"DISCA.A^H14","alternative_rics":"DISCA.II^G10;DISCA.W^E14","isin":"US9344231041","requested_start":"2010-03-01","requested_end":"2022-04-08"},
{"ticker":"DISCK","company":"Discovery Ord Shs Series C, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"DISCK.O^D22","alternative_rics":"DISCK.ARC^D22;DISCK.A^D22;DISCK.BAT^D22;DISCK.BT1^D22;DISCK.BYX^D22;DISCK.B^D22;DISCK.C^D22;DISCK.DF^D22;DISCK.DG^D22;DISCK.DY^D22;DISCK.EI^D22;DISCK.ITC^D22;DISCK.LTS^D22;DISCK.MEM^D22;DISCK.MP^D22;DISCK.MW^D22;DISCK.NB^D22;DISCK.NQT^D22;DISCK.N^D22;DISCK.OQ^D22;DISCK.PH^D22;DISCK.P^D22;DISCK.ZY^D22;DISCK.Z^D22","isin":"US25470F3029","requested_start":"2014-08-07","requested_end":"2022-04-08"},
{"ticker":"DISH","company":"DISH Network Ord Shs Class A, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"DISH.O^A24","alternative_rics":"DISH.AOI^A24;DISH.ARC^A24;DISH.A^A24;DISH.BAT^A24;DISH.BT1^A24;DISH.BYX^A24;DISH.B^A24;DISH.C^A24;DISH.DEX^A24;DISH.DF^A24;DISH.DG^A24;DISH.DY^A24;DISH.EI^A24;DISH.ITC^A24;DISH.LTS^A24;DISH.MEM^A24;DISH.MP^A24;DISH.MW^A24;DISH.NB^A24;DISH.NOI^A24;DISH.NQT^A24;DISH.N^A24;DISH.OQ^A24;DISH.PH^A24;DISH.P^A24;DISH.ZY^A24;DISH.Z^A24","isin":"US25470M1099","requested_start":"2017-03-13","requested_end":"2023-06-16"},
{"ticker":"DNR","company":"Denbury Resources Ord Shs, Ordinary Share, Delisted, NYSE ArcaBook Equities","ric":"DNR.ARC^G20","alternative_rics":"DNR.A^G20;DNR.BAT^G20;DNR.BT1^G20;DNR.BYX^G20;DNR.B^G20;DNR.C^G20;DNR.DF^G20;DNR.DG^G20;DNR.DY^G20;DNR.EI^G20;DNR.II^G10;DNR.ITC^G20;DNR.MW^G20;DNR.NB^G20;DNR.N^G20;DNR.PH^G20;DNR.P^G20;DNR.TH^G20;DNR.W^E14;DNR.ZY^G20;DNR.Z^G20","isin":"US2479162081","requested_start":"2009-04-02","requested_end":"2015-03-20"},
{"ticker":"DRE","company":"Duke Realty REIT Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"DRE^J22","alternative_rics":"DRE.AOI^J22;DRE.ARC^J22;DRE.A^J22;DRE.BAT^J22;DRE.BT1^J22;DRE.BYX^J22;DRE.B^J22;DRE.C^J22;DRE.DF^J22;DRE.DG^J22;DRE.DY^J22;DRE.EI^J22;DRE.ITC^J22;DRE.LTS^J22;DRE.MEM^J22;DRE.MP^J22;DRE.NB^J22;DRE.NOI^J22;DRE.NQT^J22;DRE.N^J22;DRE.PH^J22;DRE.P^J22;DRE.ZY^J22;DRE.Z^J22","isin":"US2644115055","requested_start":"2017-07-26","requested_end":"2022-09-30"},
{"ticker":"DTV","company":"DirecTV Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"DTV.O^G15","alternative_rics":"DTV.A^G15;DTV.A^I12;DTV.BAT^G15;DTV.BYX^G15;DTV.B^G15;DTV.C^G14;DTV.DF^G15;DTV.DG^G15;DTV.DY^G15;DTV.II^G10;DTV.ITC^G15;DTV.MW^G15;DTV.NB^G15;DTV.OQ^G15;DTV.PH^B09;DTV.PH^G15;DTV.P^G15;DTV.W^E14;DTV.ZY^G15;DTV.Z^G15","isin":"US25490A3095","requested_start":"2008-01-02","requested_end":"2015-07-24"},
{"ticker":"EA","company":"Electronic Arts Ord Shs, Ordinary Share, Delisted, NYSE AMEX IMBALANCE","ric":"EA.AOI^H26","alternative_rics":"EA.ARC^H26;EA.A^H26;EA.A^J16;EA.BAT^H26;EA.BLUE^H26;EA.BT1^H26;EA.BYX^H26;EA.B^H26;EA.C^H26;EA.DEX^H26;EA.DF^H26;EA.DG^H26;EA.DY^H26;EA.EI^H26;EA.ITC^H26;EA.LTS^H26;EA.MEM^H26;EA.MP^H26;EA.MW^H26;EA.NB^H26;EA.NIB^H26;EA.NOI^H26;EA.NQT^H26;EA.N^H26;EA.OQ^H26;EA.O^H26;EA.PH^H26;EA.P^H26;EA.TXS^H26;EA.W^E14;EA.XN^H26;EA.ZY^H26;EA.Z^H26","isin":"US2855121099","requested_start":"2008-01-02","requested_end":"2026-08-04"},
{"ticker":"EKDKQ","company":"Eastman Kodak Ord Shs, Ordinary Share, Delisted, OTC MARKETS GROUP L1 AND L2","ric":"EKDKQ.PK^I13","alternative_rics":"EKDKQ.PQ^I13","isin":"US2774611097","requested_start":"2008-01-02","requested_end":"2010-12-17"},
{"ticker":"EMC","company":"EMC Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"EMC^I16","alternative_rics":"EMC.BAT^I16;EMC.BYX^I16;EMC.B^I16;EMC.C^I16;EMC.DF^I16;EMC.DG^I16;EMC.DY^I16;EMC.EI^I16;EMC.II^G10;EMC.ITC^I16;EMC.MW^I16;EMC.NB^I16;EMC.N^I16;EMC.PH^B09;EMC.PH^I16;EMC.P^I16;EMC.TH^I16;EMC.W^E14;EMC.ZY^I16;EMC.Z^I16","isin":"US2686481027","requested_start":"2008-01-02","requested_end":"2016-09-06"},
{"ticker":"ENDP","company":"Endo International Ord Shs, Ordinary Share, Delisted, NYSE ArcaBook Equities","ric":"ENDP.ARC^H22","alternative_rics":"ENDP.A^H22;ENDP.BAT^H22;ENDP.BT1^H22;ENDP.BYX^H22;ENDP.B^H22;ENDP.C^H22;ENDP.DF^H22;ENDP.DG^H22;ENDP.DY^H22;ENDP.EI^H22;ENDP.ITC^H22;ENDP.LTS^H22;ENDP.MEM^H22;ENDP.MP^H22;ENDP.MW^H22;ENDP.NB^H22;ENDP.NQT^H22;ENDP.N^H22;ENDP.OQ^H22;ENDP.PH^H22;ENDP.P^H22;ENDP.ZY^H22;ENDP.Z^H22","isin":"IE00BJ3V9050","requested_start":"2015-01-27","requested_end":"2017-03-01"},
{"ticker":"EQR","company":"Vivmark Residential Ord Shs, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"EQR.II^G10","alternative_rics":"EQR.PH^B09;EQR.W^E14","isin":"US29476L1070","requested_start":"2008-01-02","requested_end":"2026-08-17"},
{"ticker":"ESRX","company":"Express Scripts Holding Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"ESRX.O^L18","alternative_rics":"ESRX.ARC^L18;ESRX.A^I12;ESRX.A^L18;ESRX.BAT^L18;ESRX.BT1^L18;ESRX.BYX^L18;ESRX.B^L18;ESRX.C^L18;ESRX.DF^L18;ESRX.DG^L18;ESRX.DY^L18;ESRX.EI^L18;ESRX.II^G10;ESRX.ITC^L18;ESRX.MW^L18;ESRX.NB^L18;ESRX.N^L18;ESRX.OQ^L18;ESRX.PH^B09;ESRX.PH^L18;ESRX.P^L18;ESRX.W^E14;ESRX.ZY^L18;ESRX.Z^L18","isin":"US30219G1085","requested_start":"2008-01-02","requested_end":"2018-12-20"},
{"ticker":"ESV","company":"Valaris Ord Shs Class A, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"ESV.II^G10","alternative_rics":"ESV.PH^B09;ESV.W^E14","isin":"GB00BJVJZD68","requested_start":"2008-01-02","requested_end":"2016-03-29"},
{"ticker":"ETFC","company":"E TRADE Financial Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"ETFC.O^J20","alternative_rics":"ETFC.ARC^J20;ETFC.A^J16;ETFC.A^J20;ETFC.BAT^J20;ETFC.BT1^J20;ETFC.BYX^J20;ETFC.B^J20;ETFC.C^J20;ETFC.DF^J20;ETFC.DG^J20;ETFC.DY^J20;ETFC.EI^J20;ETFC.II^G10;ETFC.ITC^J20;ETFC.LTS^J20;ETFC.MEM^J20;ETFC.MW^J20;ETFC.NB^J20;ETFC.N^J20;ETFC.OQ^J20;ETFC.PH^B09;ETFC.PH^J20;ETFC.P^J20;ETFC.W^E14;ETFC.ZY^J20;ETFC.Z^J20","isin":"US2692464017","requested_start":"2008-01-02","requested_end":"2020-10-06"},
{"ticker":"FDO","company":"Family Dollar Stores Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"FDO^G15","alternative_rics":"FDO.BAT^G15;FDO.BYX^G15;FDO.B^G15;FDO.C^G14;FDO.DF^G15;FDO.DG^G15;FDO.DY^G15;FDO.II^G10;FDO.ITC^G15;FDO.MW^G15;FDO.NB^G15;FDO.N^G15;FDO.PH^B09;FDO.PH^G15;FDO.P^G15;FDO.TH^G15;FDO.W^E14;FDO.ZY^G15;FDO.Z^G15","isin":"US3070001090","requested_start":"2008-01-02","requested_end":"2015-07-06"},
{"ticker":"FI","company":"Fiserv Ord Shs, Ordinary Share, Delisted, NASDAQ INTERMARKET","ric":"FI.TH^K25","alternative_rics":"","isin":"US3377381088","requested_start":"2023-06-07","requested_end":"2025-11-10"},
{"ticker":"FISV","company":"Fiserv Inc, Ordinary Share, NASDAQ Global Select Consolidated","ric":"FISV.O","alternative_rics":"FISV.A;FISV.AOI;FISV.ARC;FISV.A^I12;FISV.B;FISV.BAT;FISV.BLUE;FISV.BT1;FISV.BYX;FISV.C;FISV.DEX;FISV.DF;FISV.DG;FISV.DY;FISV.EI;FISV.II^G10;FISV.ITC;FISV.LTS;FISV.MEM;FISV.MP;FISV.MW;FISV.N;FISV.NB;FISV.NIB;FISV.NOI;FISV.NQT;FISV.N^F23;FISV.OQ;FISV.P;FISV.PH;FISV.PH^B09;FISV.TXS;FISV.W^E14;FISV.XN;FISV.Z;FISV.ZY","isin":"US3377381088","requested_start":"2008-01-02","requested_end":"2026-08-18"},
{"ticker":"FL","company":"Foot Locker Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"FL^I25","alternative_rics":"FL.AOI^I25;FL.ARC^I25;FL.A^I25;FL.BAT^I25;FL.BLUE^I25;FL.BT1^I25;FL.BYX^I25;FL.B^I25;FL.C^I25;FL.DEX^I25;FL.DF^I25;FL.DG^I25;FL.DY^I25;FL.EI^I25;FL.ITC^I25;FL.LTS^I25;FL.MEM^I25;FL.MP^I25;FL.MW^I25;FL.NB^I25;FL.NOI^I25;FL.NQT^I25;FL.N^I25;FL.PH^I25;FL.P^I25;FL.TH^I25;FL.ZY^I25;FL.Z^I25","isin":"US3448491049","requested_start":"2016-04-04","requested_end":"2019-08-08"},
{"ticker":"FLIR","company":"FLIR Systems Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"FLIR.O^E21","alternative_rics":"FLIR.ARC^E21;FLIR.A^E21;FLIR.A^I12;FLIR.BAT^E21;FLIR.BT1^E21;FLIR.BYX^E21;FLIR.B^E21;FLIR.C^E21;FLIR.DF^E21;FLIR.DG^E21;FLIR.DY^E21;FLIR.EI^E21;FLIR.II^G10;FLIR.ITC^E21;FLIR.LTS^E21;FLIR.MEM^E21;FLIR.MP^E21;FLIR.MW^E21;FLIR.NB^E21;FLIR.N^E21;FLIR.OQ^E21;FLIR.PH^B09;FLIR.PH^E21;FLIR.P^E21;FLIR.W^E14;FLIR.ZY^E21;FLIR.Z^E21","isin":"US3024451011","requested_start":"2009-01-02","requested_end":"2021-05-13"},
{"ticker":"FOX","company":"Fox Corporation, Ordinary Share, Class B, NASDAQ Global Select Consolidated","ric":"FOX.O","alternative_rics":"FOX.A;FOX.AOI;FOX.ARC;FOX.B;FOX.BAT;FOX.BLUE;FOX.BT1;FOX.BYX;FOX.C;FOX.DEX;FOX.DF;FOX.DG;FOX.DY;FOX.EI;FOX.ITC;FOX.LTS;FOX.MEM;FOX.MP;FOX.MW;FOX.N;FOX.NB;FOX.NIB;FOX.NOI;FOX.NQT;FOX.OQ;FOX.P;FOX.PH;FOX.TXS;FOX.XN;FOX.Z;FOX.ZY","isin":"US35137L2043","requested_start":"2015-09-21","requested_end":"2026-08-18"},
{"ticker":"FRC","company":"First Republic Bank Ord Shs, Ordinary Share, Delisted, NYSE AMEX IMBALANCE","ric":"FRC.AOI^E23","alternative_rics":"FRC.ARC^E23;FRC.A^E23;FRC.BAT^E23;FRC.BT1^E23;FRC.BYX^E23;FRC.B^E23;FRC.C^E23;FRC.DF^E23;FRC.DG^E23;FRC.DY^E23;FRC.EI^E23;FRC.ITC^E23;FRC.LTS^E23;FRC.MEM^E23;FRC.MP^E23;FRC.MW^E23;FRC.NB^E23;FRC.NOI^E23;FRC.NQT^E23;FRC.N^E23;FRC.PH^E23;FRC.P^E23;FRC.TH^E23;FRC.ZY^E23;FRC.Z^E23","isin":"US33616C1009","requested_start":"2019-01-02","requested_end":"2023-05-03"},
{"ticker":"FRX","company":"Forest Laboratories Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"FRX^G14","alternative_rics":"FRX.BAT^G14;FRX.BYX^G14;FRX.B^G14;FRX.C^G14;FRX.DF^G14;FRX.DG^G14;FRX.DY^G14;FRX.II^G10;FRX.ITC^G14;FRX.MW^G14;FRX.NB^G14;FRX.N^G14;FRX.PH^B09;FRX.PH^G14;FRX.P^G14;FRX.TH^G14;FRX.W^E14;FRX.ZY^G14;FRX.Z^G14","isin":"US3458381064","requested_start":"2008-01-02","requested_end":"2014-06-30"},
{"ticker":"FTR","company":"Frontier Communications Ord Shs, Ordinary Share, Delisted, NYSE ArcaBook Equities","ric":"FTR.ARC^D20","alternative_rics":"FTR.A^D20;FTR.BAT^D20;FTR.BT1^D20;FTR.BYX^D20;FTR.B^D20;FTR.C^D20;FTR.DF^D20;FTR.DG^D20;FTR.DY^D20;FTR.EI^D20;FTR.II^G10;FTR.ITC^D20;FTR.MW^D20;FTR.NB^D20;FTR.N^D20;FTR.OQ^D20;FTR.PH^B09;FTR.PH^D20;FTR.P^D20;FTR.TH^L11;FTR.W^E14;FTR.ZY^D20;FTR.Z^D20","isin":"US35906A3068","requested_start":"2008-01-02","requested_end":"2017-03-17"},
{"ticker":"GENZ","company":"Genzyme Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"GENZ.O^D11","alternative_rics":"GENZ.A^D11;GENZ.B^D11;GENZ.C^D11;GENZ.DF^D11;GENZ.DG^D11;GENZ.DY^D11;GENZ.II^G10;GENZ.MW^D11;GENZ.OQ^D11;GENZ.PH^B09;GENZ.PH^D11;GENZ.P^D11;GENZ.W^D11;GENZ.ZY^D11;GENZ.Z^D11","isin":"US3729171047","requested_start":"2008-01-02","requested_end":"2011-04-01"},
{"ticker":"GGP","company":"GGP Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"GGP^H18","alternative_rics":"GGP.A^H18;GGP.BAT^H18;GGP.BT1^H18;GGP.BYX^H18;GGP.B^D09;GGP.B^H18;GGP.C^D09;GGP.C^H18;GGP.DF^D09;GGP.DF^H18;GGP.DG^H18;GGP.DY^H18;GGP.EI^H18;GGP.II^D09;GGP.ITC^H18;GGP.MW^H18;GGP.NB^H18;GGP.N^D09;GGP.N^H18;GGP.PH^B09;GGP.PH^H18;GGP.P^D09;GGP.P^H18;GGP.TH^H18;GGP.W^D09;GGP.W^E14;GGP.ZY^H18;GGP.Z^D09;GGP.Z^H18","isin":"US36174X1019","requested_start":"2008-01-02","requested_end":"2018-08-27"},
{"ticker":"GMCR","company":"Keurig Green Mountain Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"GMCR.O^C16","alternative_rics":"GMCR.BAT^C16;GMCR.BYX^C16;GMCR.B^C16;GMCR.C^C16;GMCR.DF^C16;GMCR.DG^C16;GMCR.DY^C16;GMCR.ITC^C16;GMCR.MW^C16;GMCR.NB^C16;GMCR.OQ^C16;GMCR.PH^C16;GMCR.P^C16;GMCR.W^E14;GMCR.ZY^C16;GMCR.Z^C16","isin":"US49271M1009","requested_start":"2014-03-24","requested_end":"2016-03-02"},
{"ticker":"GPS","company":"Gap Ord Shs, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"GPS.II^G10","alternative_rics":"GPS.PH^B09;GPS.W^E14","isin":"US3647601083","requested_start":"2008-01-02","requested_end":"2022-02-01"},
{"ticker":"GR","company":"Goodrich Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"GR.N^G12","alternative_rics":"GR.B^G12;GR.C^G12;GR.DF^G12;GR.DG^G12;GR.DY^G12;GR.II^G10;GR.MW^G12;GR.PH^B09;GR.PH^G12;GR.P^G12;GR.TH^G12;GR.W^G12;GR.ZY^G12;GR.Z^G12;GR^G12","isin":"US3823881061","requested_start":"2008-01-02","requested_end":"2012-07-26"},
{"ticker":"HAR","company":"Harman International Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"HAR^C17","alternative_rics":"HAR.BAT^C17;HAR.BYX^C17;HAR.B^C17;HAR.C^C17;HAR.DF^C17;HAR.DG^C17;HAR.DY^C17;HAR.EI^C17;HAR.II^G10;HAR.ITC^C17;HAR.MW^C17;HAR.NB^C17;HAR.N^C17;HAR.PH^B09;HAR.PH^C17;HAR.P^C17;HAR.TH^C17;HAR.W^E14;HAR.ZY^C17;HAR.Z^C17","isin":"US4130861093","requested_start":"2008-01-02","requested_end":"2017-03-10"},
{"ticker":"HBI","company":"Hanesbrands Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"HBI^L25","alternative_rics":"HBI.AOI^L25;HBI.ARC^L25;HBI.A^L25;HBI.BAT^L25;HBI.BLUE^L25;HBI.BT1^L25;HBI.BYX^L25;HBI.B^L25;HBI.C^L25;HBI.DEX^L25;HBI.DF^L25;HBI.DG^L25;HBI.DY^L25;HBI.EI^L25;HBI.ITC^L25;HBI.LTS^L25;HBI.MEM^L25;HBI.MP^L25;HBI.MW^L25;HBI.NB^L25;HBI.NOI^L25;HBI.NQT^L25;HBI.N^L25;HBI.PH^L25;HBI.P^L25;HBI.TH^L25;HBI.XN^L25;HBI.ZY^L25;HBI.Z^L25","isin":"US4103451021","requested_start":"2015-03-23","requested_end":"2021-12-17"},
{"ticker":"HCBK","company":"Hudson City Bancorp Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"HCBK.O^K15","alternative_rics":"HCBK.A^K15;HCBK.BAT^K15;HCBK.BYX^K15;HCBK.B^K15;HCBK.C^G14;HCBK.DF^K15;HCBK.DG^K15;HCBK.DY^K15;HCBK.II^G10;HCBK.ITC^K15;HCBK.MW^K15;HCBK.NB^K15;HCBK.OQ^K15;HCBK.PH^B09;HCBK.PH^K15;HCBK.P^K15;HCBK.W^E14;HCBK.ZY^K15;HCBK.Z^K15","isin":"US4436831071","requested_start":"2008-01-02","requested_end":"2015-10-30"},
{"ticker":"HES","company":"Hess Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"HES^G25","alternative_rics":"HES.AOI^G25;HES.ARC^G25;HES.A^G25;HES.BAT^G25;HES.BLUE^G25;HES.BT1^G25;HES.BYX^G25;HES.B^G25;HES.C^G25;HES.DEX^G25;HES.DF^G25;HES.DG^G25;HES.DY^G25;HES.EI^G25;HES.II^G10;HES.ITC^G25;HES.LTS^G25;HES.MEM^G25;HES.MP^G25;HES.MW^G25;HES.NB^G25;HES.NOI^G25;HES.NQT^G25;HES.N^G25;HES.PH^B09;HES.PH^G25;HES.P^G25;HES.TH^G25;HES.W^E14;HES.ZY^G25;HES.Z^G25","isin":"US42809H1077","requested_start":"2008-01-02","requested_end":"2025-07-22"},
{"ticker":"HET","company":"Caesars Entertainment Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"HET^A08","alternative_rics":"HET.C^A08;HET.DF^A08;HET.II^A08;HET.MW^A08;HET.N^A08;HET.PH^A08;HET.P^A08;HET.TH^A08;HET.W^A08","isin":"US4136191073","requested_start":"2008-01-02","requested_end":"2008-01-28"},
{"ticker":"HNZ","company":"HJ Heinz Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"HNZ^F13","alternative_rics":"HNZ.B^F13;HNZ.C^F13;HNZ.DF^F13;HNZ.DG^F13;HNZ.DY^F13;HNZ.II^G10;HNZ.MW^F13;HNZ.NB^F13;HNZ.N^F13;HNZ.PH^B09;HNZ.PH^F13;HNZ.P^F13;HNZ.TH^F13;HNZ.W^F13;HNZ.ZY^F13;HNZ.Z^F13","isin":"US4230741039","requested_start":"2008-01-02","requested_end":"2013-06-06"},
{"ticker":"HOLX","company":"Hologic Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"HOLX.O^D26","alternative_rics":"HOLX.AOI^D26;HOLX.ARC^D26;HOLX.A^D26;HOLX.BAT^D26;HOLX.BLUE^D26;HOLX.BT1^D26;HOLX.BYX^D26;HOLX.B^D26;HOLX.C^D26;HOLX.DEX^D26;HOLX.DF^D26;HOLX.DG^D26;HOLX.DY^D26;HOLX.EI^D26;HOLX.ITC^D26;HOLX.LTS^D26;HOLX.MEM^D26;HOLX.MP^D26;HOLX.MW^D26;HOLX.NB^D26;HOLX.NOI^D26;HOLX.NQT^D26;HOLX.N^D26;HOLX.OQ^D26;HOLX.PH^D26;HOLX.P^D26;HOLX.XN^D26;HOLX.ZY^D26;HOLX.Z^D26","isin":"US4364401012","requested_start":"2016-03-30","requested_end":"2026-04-08"},
{"ticker":"HOT","company":"Starwood Hotels & Resorts Worldwide Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"HOT^I16","alternative_rics":"HOT.BAT^I16;HOT.BYX^I16;HOT.B^I16;HOT.C^I16;HOT.DF^I16;HOT.DG^I16;HOT.DY^I16;HOT.EI^I16;HOT.II^G10;HOT.ITC^I16;HOT.MW^I16;HOT.NB^I16;HOT.N^I16;HOT.PH^B09;HOT.PH^I16;HOT.P^I16;HOT.TH^I16;HOT.W^E14;HOT.ZY^I16;HOT.Z^I16","isin":"US85590A4013","requested_start":"2008-01-02","requested_end":"2016-09-22"},
{"ticker":"HPC","company":"Hercules Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"HPC.N^K08","alternative_rics":"HPC.C^K08;HPC.DF^K08;HPC.II^K08;HPC.MW^K08;HPC.PH^K08;HPC.P^K08;HPC.TH^K08;HPC.W^K08;HPC.Z^K08;HPC^K08","isin":"US4270561065","requested_start":"2008-01-02","requested_end":"2008-11-13"},
{"ticker":"HRS","company":"L3Harris Technologies Ord Shs, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"HRS.II^G10","alternative_rics":"HRS.PH^B09;HRS.W^E14","isin":"US5024311095","requested_start":"2008-09-22","requested_end":"2019-05-31"},
{"ticker":"HSH","company":"Hillshire Brands Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"HSH^H14","alternative_rics":"HSH.BAT^H14;HSH.BYX^H14;HSH.B^H14;HSH.C^G14;HSH.DF^H14;HSH.DG^H14;HSH.DY^H14;HSH.ITC^H14;HSH.MW^H14;HSH.NB^H14;HSH.N^H14;HSH.PH^H14;HSH.P^H14;HSH.TH^H14;HSH.W^E14;HSH.ZY^H14;HSH.Z^H14","isin":"US4325891095","requested_start":"2008-01-02","requested_end":"2012-06-28"},
{"ticker":"HSP","company":"Hospira Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"HSP^I15","alternative_rics":"HSP.BAT^I15;HSP.BYX^I15;HSP.B^I15;HSP.C^G14;HSP.DF^I15;HSP.DG^I15;HSP.DY^I15;HSP.II^G10;HSP.ITC^I15;HSP.MW^I15;HSP.NB^I15;HSP.N^I15;HSP.PH^B09;HSP.PH^I15;HSP.P^I15;HSP.TH^I15;HSP.W^E14;HSP.ZY^I15;HSP.Z^I15","isin":"US4410601003","requested_start":"2008-01-02","requested_end":"2015-09-02"},
{"ticker":"IGT","company":"International Game Technology Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"IGT^D15","alternative_rics":"IGT.BAT^D15;IGT.BYX^D15;IGT.B^D15;IGT.C^G14;IGT.DF^D15;IGT.DG^D15;IGT.DY^D15;IGT.II^G10;IGT.ITC^D15;IGT.MW^D15;IGT.NB^D15;IGT.N^D15;IGT.PH^B09;IGT.PH^D15;IGT.P^D15;IGT.TH^D15;IGT.W^E14;IGT.ZY^D15;IGT.Z^D15","isin":"US4599021023","requested_start":"2008-01-02","requested_end":"2014-06-19"},
{"ticker":"INFO","company":"IHS Markit Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"INFO.K^B22","alternative_rics":"INFO.ARC^B22;INFO.A^B22;INFO.BAT^B22;INFO.BT1^B22;INFO.BYX^B22;INFO.B^B22;INFO.C^B22;INFO.DF^B22;INFO.DG^B22;INFO.DY^B22;INFO.EI^B22;INFO.ITC^B22;INFO.LTS^B22;INFO.MEM^B22;INFO.MP^B22;INFO.MW^B22;INFO.NB^B22;INFO.NQT^B22;INFO.N^B22;INFO.N^G19;INFO.PH^B22;INFO.P^B22;INFO.TH^B22;INFO.ZY^B22;INFO.Z^B22","isin":"BMG475671050","requested_start":"2017-06-02","requested_end":"2022-03-01"},
{"ticker":"IPG","company":"Interpublic Group of Companies Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"IPG^K25","alternative_rics":"IPG.AOI^K25;IPG.ARC^K25;IPG.A^K25;IPG.BAT^K25;IPG.BLUE^K25;IPG.BT1^K25;IPG.BYX^K25;IPG.B^K25;IPG.C^K25;IPG.DEX^K25;IPG.DF^K25;IPG.DG^K25;IPG.DY^K25;IPG.EI^K25;IPG.II^G10;IPG.ITC^K25;IPG.LTS^K25;IPG.MEM^K25;IPG.MP^K25;IPG.MW^K25;IPG.NB^K25;IPG.NOI^K25;IPG.NQT^K25;IPG.N^K25;IPG.PH^B09;IPG.PH^K25;IPG.P^K25;IPG.TH^K25;IPG.W^E14;IPG.XN^K25;IPG.ZY^K25;IPG.Z^K25","isin":"US4606901001","requested_start":"2008-01-02","requested_end":"2025-11-26"},
{"ticker":"JAVA","company":"Sun Microsystems Ord Shs, Ordinary Share, Delisted, NASDAQ Stock Exchange Global Select Market","ric":"JAVA.OQ^B10","alternative_rics":"JAVA.B^B10;JAVA.C^B10;JAVA.DF^B10;JAVA.II^B10;JAVA.MW^B10;JAVA.O^B10;JAVA.PH^B09;JAVA.P^B10;JAVA.W^B10;JAVA.Z^B10","isin":"US8668102036","requested_start":"2008-01-02","requested_end":"2010-01-26"},
{"ticker":"JCP","company":"OLD COPPER Ord Shs, Ordinary Share, Delisted, NYSE ArcaBook Equities","ric":"JCP.ARC^E20","alternative_rics":"JCP.A^E20;JCP.BAT^E20;JCP.BT1^E20;JCP.BYX^E20;JCP.B^E20;JCP.C^E20;JCP.DF^E20;JCP.DG^E20;JCP.DY^E20;JCP.EI^E20;JCP.II^G10;JCP.ITC^E20;JCP.MW^E20;JCP.NB^E20;JCP.N^E20;JCP.PH^B09;JCP.PH^E20;JCP.P^E20;JCP.TH^E20;JCP.W^E14;JCP.ZY^E20;JCP.Z^E20","isin":"US6795351047","requested_start":"2008-01-02","requested_end":"2013-11-29"},
{"ticker":"JEC","company":"Jacobs Solutions Ord Shs, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"JEC.II^G10","alternative_rics":"JEC.PH^B09;JEC.W^E14","isin":"US46982L1089","requested_start":"2008-01-02","requested_end":"2019-12-09"},
{"ticker":"JNPR","company":"Juniper Networks Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"JNPR.K^G25","alternative_rics":"JNPR.AOI^G25;JNPR.ARC^G25;JNPR.A^G25;JNPR.BAT^G25;JNPR.BLUE^G25;JNPR.BT1^G25;JNPR.BYX^G25;JNPR.B^G25;JNPR.C^G25;JNPR.DEX^G25;JNPR.DF^G25;JNPR.DG^G25;JNPR.DY^G25;JNPR.EI^G25;JNPR.II^G10;JNPR.ITC^G25;JNPR.LTS^G25;JNPR.MEM^G25;JNPR.MP^G25;JNPR.MW^G25;JNPR.NB^G25;JNPR.NOI^G25;JNPR.NQT^G25;JNPR.N^G25;JNPR.PH^B09;JNPR.PH^G25;JNPR.P^G25;JNPR.TH^G25;JNPR.W^E14;JNPR.ZY^G25;JNPR.Z^G25","isin":"US48203R1041","requested_start":"2008-01-02","requested_end":"2025-07-08"},
{"ticker":"JNS","company":"Janus Capital Group Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"JNS^E17","alternative_rics":"JNS.BAT^E17;JNS.BYX^E17;JNS.B^E17;JNS.C^E17;JNS.DF^E17;JNS.DG^E17;JNS.DY^E17;JNS.EI^E17;JNS.II^G10;JNS.ITC^E17;JNS.MW^E17;JNS.NB^E17;JNS.N^E17;JNS.PH^B09;JNS.PH^E17;JNS.P^E17;JNS.TH^E17;JNS.W^E14;JNS.ZY^E17;JNS.Z^E17","isin":"US47102X1054","requested_start":"2008-01-02","requested_end":"2011-11-22"},
{"ticker":"JNY","company":"Jones Group Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"JNY.N^D14","alternative_rics":"JNY.B^D14;JNY.C^D14;JNY.DF^D14;JNY.DG^D14;JNY.DY^D14;JNY.II^G10;JNY.ITC^D14;JNY.MW^D14;JNY.NB^D14;JNY.PH^B09;JNY.PH^D14;JNY.P^D14;JNY.TH^D14;JNY.W^D14;JNY.ZY^D14;JNY.Z^D14;JNY^D14","isin":"US48020T1016","requested_start":"2008-01-02","requested_end":"2009-03-03"},
{"ticker":"JOY","company":"Joy Global Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"JOY^D17","alternative_rics":"JOY.BAT^D17;JOY.BYX^D17;JOY.B^D17;JOY.C^D17;JOY.DF^D17;JOY.DG^D17;JOY.DY^D17;JOY.EI^D17;JOY.ITC^D17;JOY.MW^D17;JOY.NB^D17;JOY.N^D17;JOY.PH^D17;JOY.P^D17;JOY.TH^D17;JOY.W^E14;JOY.ZY^D17;JOY.Z^D17","isin":"US4811651086","requested_start":"2011-02-28","requested_end":"2015-10-07"},
{"ticker":"JWN","company":"Nordstrom Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"JWN^E25","alternative_rics":"JWN.AOI^E25;JWN.ARC^E25;JWN.A^E25;JWN.BAT^E25;JWN.BLUE^E25;JWN.BT1^E25;JWN.BYX^E25;JWN.B^E25;JWN.C^E25;JWN.DEX^E25;JWN.DF^E25;JWN.DG^E25;JWN.DY^E25;JWN.EI^E25;JWN.II^G10;JWN.ITC^E25;JWN.LTS^E25;JWN.MEM^E25;JWN.MP^E25;JWN.MW^E25;JWN.NB^E25;JWN.NOI^E25;JWN.NQT^E25;JWN.N^E25;JWN.PH^B09;JWN.PH^E25;JWN.P^E25;JWN.TH^E25;JWN.W^E14;JWN.ZY^E25;JWN.Z^E25","isin":"US6556641008","requested_start":"2008-01-02","requested_end":"2020-06-19"},
{"ticker":"K","company":"Kellanova Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"K^L25","alternative_rics":"K.AOI^L25;K.ARC^L25;K.A^L25;K.BAT^L25;K.BLUE^L25;K.BT1^L25;K.BYX^L25;K.B^L25;K.C^L25;K.DEX^L25;K.DF^L25;K.DG^L25;K.DY^L25;K.EI^L25;K.II^G10;K.ITC^L25;K.LTS^L25;K.MEM^L25;K.MP^L25;K.MW^L25;K.NB^L25;K.NOI^L25;K.NQT^L25;K.N^L25;K.PH^B09;K.PH^L25;K.P^L25;K.TH^L25;K.W^E14;K.XN^L25;K.ZY^L25;K.Z^L25","isin":"US4878361082","requested_start":"2008-01-02","requested_end":"2025-12-10"},
{"ticker":"KATE","company":"Kate Spade Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"KATE.K^G17","alternative_rics":"KATE.BAT^G17;KATE.BYX^G17;KATE.B^G17;KATE.C^G17;KATE.DF^G17;KATE.DG^G17;KATE.DY^G17;KATE.EI^G17;KATE.ITC^G17;KATE.MW^G17;KATE.NB^G17;KATE.N^G17;KATE.PH^G17;KATE.P^G17;KATE.TH^G17;KATE.W^E14;KATE.ZY^G17;KATE.Z^G17","isin":"US4858651098","requested_start":"2008-01-02","requested_end":"2008-12-01"},
{"ticker":"KRFT","company":"Kraft Foods Group Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"KRFT.O^G15","alternative_rics":"KRFT.A^G15;KRFT.BAT^G15;KRFT.BYX^G15;KRFT.B^G15;KRFT.C^G14;KRFT.DF^G15;KRFT.DG^G15;KRFT.DY^G15;KRFT.ITC^G15;KRFT.MW^G15;KRFT.NB^G15;KRFT.OQ^G15;KRFT.PH^G15;KRFT.P^G15;KRFT.W^E14;KRFT.ZY^G15;KRFT.Z^G15","isin":"US50076Q1067","requested_start":"2012-10-02","requested_end":"2015-07-02"},
{"ticker":"KSU","company":"Kansas City Southern Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"KSU^L21","alternative_rics":"KSU.ARC^L21;KSU.A^L21;KSU.BAT^L21;KSU.BT1^L21;KSU.BYX^L21;KSU.B^L21;KSU.C^L21;KSU.DF^L21;KSU.DG^L21;KSU.DY^L21;KSU.EI^L21;KSU.ITC^L21;KSU.LTS^L21;KSU.MEM^L21;KSU.MP^L21;KSU.MW^L21;KSU.NB^L21;KSU.NQT^L21;KSU.N^L21;KSU.PH^L21;KSU.P^L21;KSU.TH^L21;KSU.W^E14;KSU.ZY^L21;KSU.Z^L21","isin":"US4851703029","requested_start":"2013-05-24","requested_end":"2021-12-13"},
{"ticker":"LEG","company":"Leggett & Platt Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"LEG^H26","alternative_rics":"LEG.AOI^H26;LEG.ARC^H26;LEG.A^H26;LEG.BAT^H26;LEG.BLUE^H26;LEG.BT1^H26;LEG.BYX^H26;LEG.B^H26;LEG.C^H26;LEG.DEX^H26;LEG.DF^H26;LEG.DG^H26;LEG.DY^H26;LEG.EI^H26;LEG.II^G10;LEG.ITC^H26;LEG.LTS^H26;LEG.MEM^H26;LEG.MP^H26;LEG.MW^H26;LEG.NB^H26;LEG.NIB^H26;LEG.NOI^H26;LEG.NQT^H26;LEG.N^H26;LEG.PH^B09;LEG.PH^H26;LEG.P^H26;LEG.TH^H26;LEG.TXS^H26;LEG.W^E14;LEG.XN^H26;LEG.ZY^H26;LEG.Z^H26","isin":"US5246601075","requested_start":"2008-01-02","requested_end":"2021-12-17"},
{"ticker":"LEHMQ","company":"Lehman Brothers Holdings Ord Shs, Ordinary Share, Delisted, OTC Markets Group Inc - Limited Information","ric":"LEHMQ.PK^C12","alternative_rics":"","isin":"US5249081002","requested_start":"2008-01-02","requested_end":"2008-09-16"},
{"ticker":"LLL","company":"L3 Technologies Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"LLL^G19","alternative_rics":"LLL.ARC^G19;LLL.A^G19;LLL.BAT^G19;LLL.BT1^G19;LLL.BYX^G19;LLL.B^G19;LLL.C^G19;LLL.DF^G19;LLL.DG^G19;LLL.DY^G19;LLL.EI^G19;LLL.II^G10;LLL.ITC^G19;LLL.MW^G19;LLL.NB^G19;LLL.N^G19;LLL.PH^B09;LLL.PH^G19;LLL.P^G19;LLL.TH^G19;LLL.W^E14;LLL.ZY^G19;LLL.Z^G19","isin":"US5024131071","requested_start":"2008-01-02","requested_end":"2019-06-28"},
{"ticker":"LLTC","company":"Linear Technology Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"LLTC.O^C17","alternative_rics":"LLTC.A^I12;LLTC.BAT^C17;LLTC.BYX^C17;LLTC.B^C17;LLTC.C^C17;LLTC.DF^C17;LLTC.DG^C17;LLTC.DY^C17;LLTC.EI^C17;LLTC.II^G10;LLTC.ITC^C17;LLTC.MW^C17;LLTC.NB^C17;LLTC.OQ^C17;LLTC.PH^B09;LLTC.PH^C17;LLTC.P^C17;LLTC.W^E14;LLTC.ZY^C17;LLTC.Z^C17","isin":"US5356781063","requested_start":"2008-01-02","requested_end":"2017-03-10"},
{"ticker":"LM","company":"Legg Mason Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"LM^H20","alternative_rics":"LM.ARC^H20;LM.A^H20;LM.BAT^H20;LM.BT1^H20;LM.BYX^H20;LM.B^H20;LM.C^H20;LM.DF^H20;LM.DG^H20;LM.DY^H20;LM.EI^H20;LM.II^G10;LM.ITC^H20;LM.MW^H20;LM.NB^H20;LM.N^H20;LM.PH^B09;LM.PH^H20;LM.P^H20;LM.TH^H20;LM.W^E14;LM.ZY^H20;LM.Z^H20","isin":"US5249011058","requested_start":"2008-01-02","requested_end":"2016-12-01"},
{"ticker":"LO","company":"Lorillard Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"LO^F15","alternative_rics":"LO.BAT^F15;LO.BYX^F15;LO.B^F15;LO.C^G14;LO.DF^F15;LO.DG^F15;LO.DY^F15;LO.II^G10;LO.ITC^F15;LO.MW^F15;LO.NB^F15;LO.N^F15;LO.PH^B09;LO.PH^F15;LO.P^F15;LO.TH^F15;LO.W^E14;LO.ZY^F15;LO.Z^F15","isin":"US5441471019","requested_start":"2008-06-11","requested_end":"2015-06-11"},
{"ticker":"LVLT","company":"Level 3 Communications Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"LVLT.K^K17","alternative_rics":"LVLT.A^K17;LVLT.BAT^K17;LVLT.BT1^K17;LVLT.BYX^K17;LVLT.B^K17;LVLT.C^K17;LVLT.DF^K17;LVLT.DG^K17;LVLT.DY^K17;LVLT.EI^K17;LVLT.ITC^K17;LVLT.MW^K17;LVLT.NB^K17;LVLT.N^K17;LVLT.PH^K17;LVLT.P^K17;LVLT.TH^K17;LVLT.ZY^K17;LVLT.Z^K17","isin":"US52729N3089","requested_start":"2014-11-05","requested_end":"2017-10-12"},
{"ticker":"LXK","company":"Lexmark International Ord Shs Class A, Ordinary Share, Delisted, NYSE Consolidated","ric":"LXK^K16","alternative_rics":"LXK.BAT^K16;LXK.BYX^K16;LXK.B^K16;LXK.C^K16;LXK.DF^K16;LXK.DG^K16;LXK.DY^K16;LXK.EI^K16;LXK.II^G10;LXK.ITC^K16;LXK.MW^K16;LXK.NB^K16;LXK.N^K16;LXK.PH^B09;LXK.PH^K16;LXK.P^K16;LXK.TH^K16;LXK.W^E14;LXK.ZY^K16;LXK.Z^K16","isin":"US5297711070","requested_start":"2008-01-02","requested_end":"2012-09-28"},
{"ticker":"MDP","company":"Meredith Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"MDP^L21","alternative_rics":"MDP.ARC^L21;MDP.A^L21;MDP.BAT^L21;MDP.BT1^L21;MDP.BYX^L21;MDP.B^L21;MDP.C^L21;MDP.DF^L21;MDP.DG^L21;MDP.DY^L21;MDP.EI^L21;MDP.II^G10;MDP.ITC^L21;MDP.LTS^L21;MDP.MEM^L21;MDP.MP^L21;MDP.MW^L21;MDP.NB^L21;MDP.NQT^L21;MDP.N^L21;MDP.PH^B09;MDP.PH^L21;MDP.P^L21;MDP.TH^L21;MDP.W^E14;MDP.ZY^L21;MDP.Z^L21","isin":"US5894331017","requested_start":"2008-01-02","requested_end":"2011-01-03"},
{"ticker":"MEE","company":"Massey Energy Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"MEE^F11","alternative_rics":"MEE.B^F11;MEE.C^F11;MEE.DF^F11;MEE.DG^F11;MEE.DY^F11;MEE.II^G10;MEE.MW^F11;MEE.N^F11;MEE.PH^B09;MEE.PH^F11;MEE.P^F11;MEE.TH^F11;MEE.W^F11;MEE.ZY^F11;MEE.Z^F11","isin":"US5762061068","requested_start":"2008-06-23","requested_end":"2011-06-01"},
{"ticker":"MFE","company":"McAfee Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"MFE^C11","alternative_rics":"MFE.B^C11;MFE.C^C11;MFE.DF^C11;MFE.DG^C11;MFE.DY^C11;MFE.II^G10;MFE.MW^C11;MFE.N^C11;MFE.PH^B09;MFE.PH^C11;MFE.P^C11;MFE.TH^C11;MFE.W^C11;MFE.ZY^C11;MFE.Z^C11","isin":"US5790641063","requested_start":"2008-12-23","requested_end":"2011-02-28"},
{"ticker":"MHS","company":"Medco Health Solutions Ord Shs, Ordinary Share, Delisted, Boston Stock Exchange Inc","ric":"MHS.B^D12","alternative_rics":"MHS.C^D12;MHS.DF^D12;MHS.DG^D12;MHS.DY^D12;MHS.II^G10;MHS.MW^D12;MHS.N^D12;MHS.PH^B09;MHS.PH^D12;MHS.P^D12;MHS.TH^D12;MHS.W^D12;MHS.ZY^D12;MHS.Z^D12;MHS^D12","isin":"US58405U1025","requested_start":"2008-01-02","requested_end":"2012-03-30"},
{"ticker":"MJN","company":"Mead Johnson Nutrition Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"MJN^F17","alternative_rics":"MJN.BAT^F17;MJN.BYX^F17;MJN.B^F17;MJN.C^F17;MJN.DF^F17;MJN.DG^F17;MJN.DY^F17;MJN.EI^F17;MJN.II^G10;MJN.ITC^F17;MJN.MW^F17;MJN.NB^F17;MJN.N^F17;MJN.PH^F17;MJN.P^F17;MJN.TH^F17;MJN.W^E14;MJN.ZY^F17;MJN.Z^F17","isin":"US5828391061","requested_start":"2009-12-21","requested_end":"2017-06-14"},
{"ticker":"MMC","company":"Marsh Ord Shs, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"MMC.II^G10","alternative_rics":"MMC.PH^B09;MMC.W^E14","isin":"US5717481023","requested_start":"2008-01-02","requested_end":"2026-01-13"},
{"ticker":"MRO","company":"Marathon Oil Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"MRO^K24","alternative_rics":"MRO.AOI^K24;MRO.ARC^K24;MRO.A^K24;MRO.BAT^K24;MRO.BT1^K24;MRO.BYX^K24;MRO.B^K24;MRO.C^K24;MRO.DEX^K24;MRO.DF^K24;MRO.DG^K24;MRO.DY^K24;MRO.EI^K24;MRO.II^G10;MRO.ITC^K24;MRO.LTS^K24;MRO.MEM^K24;MRO.MP^K24;MRO.MW^K24;MRO.NB^K24;MRO.NOI^K24;MRO.NQT^K24;MRO.N^K24;MRO.PH^B09;MRO.PH^K24;MRO.P^K24;MRO.TH^K24;MRO.W^E14;MRO.ZY^K24;MRO.Z^K24","isin":"US5658491064","requested_start":"2008-01-02","requested_end":"2024-11-25"},
{"ticker":"MTLQQ","company":"Motors Liquidation Ord Shs, Ordinary Share, Delisted, OTC Markets Group Inc - Limited Information","ric":"MTLQQ.PK^D11","alternative_rics":"","isin":"US62010A1051","requested_start":"2008-01-02","requested_end":"2009-06-02"},
{"ticker":"MWV","company":"Meadwestvaco Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"MWV^G15","alternative_rics":"MWV.BAT^G15;MWV.BYX^G15;MWV.B^G15;MWV.C^G14;MWV.DF^G15;MWV.DG^G15;MWV.DY^G15;MWV.II^G10;MWV.ITC^G15;MWV.MW^G15;MWV.NB^G15;MWV.N^G15;MWV.PH^B09;MWV.PH^G15;MWV.P^G15;MWV.TH^G15;MWV.W^E14;MWV.ZY^G15;MWV.Z^G15","isin":"US5833341077","requested_start":"2008-01-02","requested_end":"2015-07-01"},
{"ticker":"MWW","company":"Monster Worldwide Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"MWW^K16","alternative_rics":"MWW.BAT^K16;MWW.BYX^K16;MWW.B^K16;MWW.C^K16;MWW.DF^K16;MWW.DG^K16;MWW.DY^K16;MWW.EI^K16;MWW.II^G10;MWW.ITC^K16;MWW.MW^K16;MWW.NB^K16;MWW.N^K16;MWW.PH^B09;MWW.PH^K16;MWW.P^K16;MWW.TH^K16;MWW.W^E14;MWW.ZY^K16;MWW.Z^K16","isin":"US6117421072","requested_start":"2008-01-02","requested_end":"2011-12-16"},
{"ticker":"MXIM","company":"Maxim Integrated Products Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"MXIM.O^H21","alternative_rics":"MXIM.ARC^H21;MXIM.A^H21;MXIM.BAT^H21;MXIM.BT1^H21;MXIM.BYX^H21;MXIM.B^H21;MXIM.C^H21;MXIM.DF^H21;MXIM.DG^H21;MXIM.DY^H21;MXIM.EI^H21;MXIM.ITC^H21;MXIM.LTS^H21;MXIM.MEM^H21;MXIM.MP^H21;MXIM.MW^H21;MXIM.NB^H21;MXIM.NQT^H21;MXIM.N^H21;MXIM.OQ^H21;MXIM.PH^H21;MXIM.P^H21;MXIM.ZY^H21;MXIM.Z^H21","isin":"US57772K1016","requested_start":"2018-12-03","requested_end":"2021-08-27"},
{"ticker":"MYL","company":"Viatris Ord Shs, Ordinary Share, Delisted, NYSE American when trading NASDAQ Global Select Mkt","ric":"MYL.A^H14","alternative_rics":"MYL.A^J16;MYL.II^G10;MYL.PH^B09;MYL.TH^L08;MYL.W^E14","isin":"US92556V1061","requested_start":"2008-01-02","requested_end":"2020-11-16"},
{"ticker":"NBL","company":"Noble Energy Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"NBL.O^J20","alternative_rics":"NBL.ARC^J20;NBL.A^J20;NBL.BAT^J20;NBL.BT1^J20;NBL.BYX^J20;NBL.B^J20;NBL.C^J20;NBL.DF^J20;NBL.DG^J20;NBL.DY^J20;NBL.EI^J20;NBL.II^G10;NBL.ITC^J20;NBL.LTS^J20;NBL.MEM^J20;NBL.MP^J20;NBL.MW^J20;NBL.NB^J20;NBL.N^J20;NBL.OQ^J20;NBL.PH^B09;NBL.PH^J20;NBL.P^J20;NBL.TH^L19;NBL.W^E14;NBL.ZY^J20;NBL.Z^J20","isin":"US6550441058","requested_start":"2008-01-02","requested_end":"2020-10-09"},
{"ticker":"NCC","company":"National City Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"NCC^A09","alternative_rics":"NCC.C^A09;NCC.DF^A09;NCC.II^A09;NCC.MW^A09;NCC.N^A09;NCC.PH^A09;NCC.P^A09;NCC.TH^A09;NCC.W^A09;NCC.Z^A09","isin":"US6354051038","requested_start":"2008-01-02","requested_end":"2008-12-31"},
{"ticker":"NFX","company":"Newfield Exploration Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"NFX^B19","alternative_rics":"NFX.ARC^B19;NFX.A^B19;NFX.BAT^B19;NFX.BT1^B19;NFX.BYX^B19;NFX.B^B19;NFX.C^B19;NFX.DF^B19;NFX.DG^B19;NFX.DY^B19;NFX.EI^B19;NFX.ITC^B19;NFX.MW^B19;NFX.NB^B19;NFX.N^B19;NFX.PH^B19;NFX.P^B19;NFX.TH^B19;NFX.W^E14;NFX.ZY^B19;NFX.Z^B19","isin":"US6512901082","requested_start":"2010-12-20","requested_end":"2019-02-14"},
{"ticker":"NLSN","company":"Nielsen Holdings Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"NLSN.K^J22","alternative_rics":"NLSN.AOI^J22;NLSN.ARC^J22;NLSN.A^J22;NLSN.BAT^J22;NLSN.BT1^J22;NLSN.BYX^J22;NLSN.B^J22;NLSN.C^J22;NLSN.DF^J22;NLSN.DG^J22;NLSN.DY^J22;NLSN.EI^J22;NLSN.ITC^J22;NLSN.LTS^J22;NLSN.MEM^J22;NLSN.MP^J22;NLSN.MW^J22;NLSN.NB^J22;NLSN.NOI^J22;NLSN.NQT^J22;NLSN.N^J22;NLSN.PH^J22;NLSN.P^J22;NLSN.TH^J22;NLSN.W^E14;NLSN.ZY^J22;NLSN.Z^J22","isin":"GB00BWFY5505","requested_start":"2013-07-09","requested_end":"2022-10-11"},
{"ticker":"NOVL","company":"Novell Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"NOVL.O^D11","alternative_rics":"NOVL.A^D11;NOVL.B^D11;NOVL.C^D11;NOVL.DF^D11;NOVL.DG^D11;NOVL.DY^D11;NOVL.II^G10;NOVL.MW^D11;NOVL.OQ^D11;NOVL.PH^B09;NOVL.PH^D11;NOVL.P^D11;NOVL.W^D11;NOVL.ZY^D11;NOVL.Z^D11","isin":"US6700061053","requested_start":"2008-01-02","requested_end":"2011-04-27"},
{"ticker":"NVLS","company":"Novellus System Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"NVLS.O^F12","alternative_rics":"NVLS.A^F12;NVLS.B^F12;NVLS.C^F12;NVLS.DF^F12;NVLS.DG^F12;NVLS.DY^F12;NVLS.II^G10;NVLS.MW^F12;NVLS.OQ^F12;NVLS.PH^B09;NVLS.PH^F12;NVLS.P^F12;NVLS.W^F12;NVLS.ZY^F12;NVLS.Z^F12","isin":"US6700081010","requested_start":"2008-01-02","requested_end":"2012-06-04"},
{"ticker":"NYX","company":"NYSE Euronext Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"NYX^K13","alternative_rics":"NYX.B^K13;NYX.C^K13;NYX.DF^K13;NYX.DG^K13;NYX.DY^K13;NYX.II^G10;NYX.ITC^K13;NYX.MW^K13;NYX.NB^K13;NYX.N^K13;NYX.PH^B09;NYX.PH^K13;NYX.P^K13;NYX.TH^K13;NYX.W^K13;NYX.ZY^K13;NYX.Z^K13","isin":"US6294911010","requested_start":"2008-01-02","requested_end":"2013-11-12"},
{"ticker":"ODP","company":"ODP Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"ODP.O^L25","alternative_rics":"ODP.AOI^L25;ODP.ARC^L25;ODP.A^L25;ODP.BAT^L25;ODP.BLUE^L25;ODP.BT1^L25;ODP.BYX^L25;ODP.B^L25;ODP.C^L25;ODP.DEX^L25;ODP.DF^L25;ODP.DG^L25;ODP.DY^L25;ODP.EI^L25;ODP.II^G10;ODP.ITC^L25;ODP.LTS^L25;ODP.MEM^L25;ODP.MP^L25;ODP.MW^L25;ODP.NB^L25;ODP.NOI^L25;ODP.NQT^L25;ODP.N^L25;ODP.OQ^L25;ODP.PH^B09;ODP.PH^L25;ODP.P^L25;ODP.TH^I14;ODP.W^E14;ODP.XN^L25;ODP.ZY^L25;ODP.Z^L25","isin":"US88337F1057","requested_start":"2008-01-02","requested_end":"2010-12-17"},
{"ticker":"OMX","company":"OfficeMax Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"OMX^K13","alternative_rics":"OMX.B^K13;OMX.C^K13;OMX.DF^K13;OMX.DG^K13;OMX.DY^K13;OMX.II^G10;OMX.ITC^K13;OMX.MW^K13;OMX.NB^K13;OMX.N^K13;OMX.PH^B09;OMX.PH^K13;OMX.P^K13;OMX.TH^K13;OMX.W^K13;OMX.ZY^K13;OMX.Z^K13","isin":"US67622P1012","requested_start":"2008-01-02","requested_end":"2008-06-20"},
{"ticker":"PARA","company":"Parabolic Technologies, Inc., Ordinary Share, Class A, NASDAQ Capital Market Consolidated","ric":"PARA.O","alternative_rics":"PARA.A;PARA.AOI;PARA.ARC;PARA.B;PARA.BAT;PARA.BLUE;PARA.BT1;PARA.BYX;PARA.C;PARA.DEX;PARA.DF;PARA.DG;PARA.DY;PARA.EI;PARA.ITC;PARA.LTS;PARA.MEM;PARA.MP;PARA.MW;PARA.N;PARA.NB;PARA.NIB;PARA.NOI;PARA.NQT;PARA.OQ;PARA.P;PARA.PH;PARA.TXS;PARA.XN;PARA.Z;PARA.ZY","isin":"US06682J8036","requested_start":"2022-02-17","requested_end":"2025-08-07"},
{"ticker":"PBCT","company":"Peoples United Financial Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"PBCT.O^D22","alternative_rics":"PBCT.ARC^D22;PBCT.A^D22;PBCT.BAT^D22;PBCT.BT1^D22;PBCT.BYX^D22;PBCT.B^D22;PBCT.C^D22;PBCT.DF^D22;PBCT.DG^D22;PBCT.DY^D22;PBCT.EI^D22;PBCT.II^G10;PBCT.ITC^D22;PBCT.LTS^D22;PBCT.MEM^D22;PBCT.MP^D22;PBCT.MW^D22;PBCT.NB^D22;PBCT.NQT^D22;PBCT.N^D22;PBCT.OQ^D22;PBCT.PH^B09;PBCT.PH^D22;PBCT.P^D22;PBCT.W^E14;PBCT.ZY^D22;PBCT.Z^D22","isin":"US7127041058","requested_start":"2008-11-13","requested_end":"2022-04-01"},
{"ticker":"PBG","company":"Pepsi Bottling Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"PBG.N^C10","alternative_rics":"PBG.B^C10;PBG.C^C10;PBG.DF^C10;PBG.II^C10;PBG.MW^C10;PBG.PH^B09;PBG.P^C10;PBG.TH^C10;PBG.W^C10;PBG.Z^C10;PBG^C10","isin":"US7134091005","requested_start":"2008-01-02","requested_end":"2010-02-26"},
{"ticker":"PCL","company":"Plum Creek Timber Company REIT Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"PCL^B16","alternative_rics":"PCL.BAT^B16;PCL.BYX^B16;PCL.B^B16;PCL.C^B16;PCL.DF^B16;PCL.DG^B16;PCL.DY^B16;PCL.II^G10;PCL.ITC^B16;PCL.MW^B16;PCL.NB^B16;PCL.N^B16;PCL.PH^B09;PCL.PH^B16;PCL.P^B16;PCL.TH^B16;PCL.W^E14;PCL.ZY^B16;PCL.Z^B16","isin":"US7292511083","requested_start":"2008-01-02","requested_end":"2016-02-19"},
{"ticker":"PCP","company":"Precision Castparts Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"PCP^B16","alternative_rics":"PCP.BAT^B16;PCP.BYX^B16;PCP.B^B16;PCP.C^B16;PCP.DF^B16;PCP.DG^B16;PCP.DY^B16;PCP.II^G10;PCP.ITC^B16;PCP.MW^B16;PCP.NB^B16;PCP.N^B16;PCP.PH^B09;PCP.PH^B16;PCP.P^B16;PCP.TH^B16;PCP.W^E14;PCP.ZY^B16;PCP.Z^B16","isin":"US7401891053","requested_start":"2008-01-02","requested_end":"2016-01-29"},
{"ticker":"PDCO","company":"Patterson Companies Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"PDCO.O^D25","alternative_rics":"PDCO.AOI^D25;PDCO.ARC^D25;PDCO.A^D25;PDCO.A^I12;PDCO.BAT^D25;PDCO.BT1^D25;PDCO.BYX^D25;PDCO.B^D25;PDCO.C^D25;PDCO.DEX^D25;PDCO.DF^D25;PDCO.DG^D25;PDCO.DY^D25;PDCO.EI^D25;PDCO.II^G10;PDCO.ITC^D25;PDCO.LTS^D25;PDCO.MEM^D25;PDCO.MP^D25;PDCO.MW^D25;PDCO.NB^D25;PDCO.NOI^D25;PDCO.NQT^D25;PDCO.N^D25;PDCO.OQ^D25;PDCO.PH^B09;PDCO.PH^D25;PDCO.P^D25;PDCO.W^E14;PDCO.ZY^D25;PDCO.Z^D25","isin":"US7033951036","requested_start":"2008-01-02","requested_end":"2018-03-16"},
{"ticker":"PETM","company":"PetSmart Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"PETM.O^C15","alternative_rics":"PETM.BAT^C15;PETM.BYX^C15;PETM.B^C15;PETM.C^G14;PETM.DF^C15;PETM.DG^C15;PETM.DY^C15;PETM.ITC^C15;PETM.MW^C15;PETM.NB^C15;PETM.OQ^C15;PETM.PH^C15;PETM.P^C15;PETM.W^E14;PETM.ZY^C15;PETM.Z^C15","isin":"US7167681060","requested_start":"2012-10-05","requested_end":"2015-03-11"},
{"ticker":"PTV","company":"Pactiv Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"PTV^K10","alternative_rics":"PTV.B^K10;PTV.C^K10;PTV.DF^K10;PTV.DG^K10;PTV.DY^K10;PTV.II^G10;PTV.MW^K10;PTV.N^K10;PTV.PH^B09;PTV.PH^K10;PTV.P^K10;PTV.TH^K10;PTV.W^K10;PTV.ZY^K10;PTV.Z^K10","isin":"US6952571056","requested_start":"2008-01-02","requested_end":"2010-11-16"},
{"ticker":"PX","company":"Praxair Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"PX^J18","alternative_rics":"PX.A^J18;PX.BAT^J18;PX.BT1^J18;PX.BYX^J18;PX.B^J18;PX.C^J18;PX.DF^J18;PX.DG^J18;PX.DY^J18;PX.EI^J18;PX.II^G10;PX.ITC^J18;PX.MW^J18;PX.NB^J18;PX.N^J18;PX.PH^B09;PX.PH^J18;PX.P^J18;PX.TH^J18;PX.W^E14;PX.ZY^J18;PX.Z^J18","isin":"US74005P1049","requested_start":"2008-01-02","requested_end":"2018-10-30"},
{"ticker":"PXD","company":"Pioneer Natural Resource Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"PXD^E24","alternative_rics":"PXD.AOI^E24;PXD.ARC^E24;PXD.A^E24;PXD.BAT^E24;PXD.BT1^E24;PXD.BYX^E24;PXD.B^E24;PXD.C^E24;PXD.DEX^E24;PXD.DF^E24;PXD.DG^E24;PXD.DY^E24;PXD.EI^E24;PXD.II^G10;PXD.ITC^E24;PXD.LTS^E24;PXD.MEM^E24;PXD.MP^E24;PXD.MW^E24;PXD.NB^E24;PXD.NOI^E24;PXD.NQT^E24;PXD.N^E24;PXD.PH^B09;PXD.PH^E24;PXD.P^E24;PXD.TH^E24;PXD.W^E14;PXD.ZY^E24;PXD.Z^E24","isin":"US7237871071","requested_start":"2008-09-24","requested_end":"2024-05-07"},
{"ticker":"QEP","company":"QEP Resources Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"QEP^C21","alternative_rics":"QEP.ARC^C21;QEP.A^C21;QEP.BAT^C21;QEP.BT1^C21;QEP.BYX^C21;QEP.B^C21;QEP.C^C21;QEP.DF^C21;QEP.DG^C21;QEP.DY^C21;QEP.EI^C21;QEP.ITC^C21;QEP.LTS^C21;QEP.MEM^C21;QEP.MP^C21;QEP.MW^C21;QEP.NB^C21;QEP.N^C21;QEP.PH^C21;QEP.P^C21;QEP.TH^C21;QEP.W^E14;QEP.ZY^C21;QEP.Z^C21","isin":"US74733V1008","requested_start":"2010-07-01","requested_end":"2015-06-30"},
{"ticker":"QLGC","company":"QLogic Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"QLGC.O^H16","alternative_rics":"QLGC.A^L13;QLGC.BAT^H16;QLGC.BYX^H16;QLGC.B^H16;QLGC.C^H16;QLGC.DF^H16;QLGC.DG^H16;QLGC.DY^H16;QLGC.II^G10;QLGC.ITC^H16;QLGC.MW^H16;QLGC.NB^H16;QLGC.OQ^H16;QLGC.PH^B09;QLGC.PH^H16;QLGC.P^H16;QLGC.W^E14;QLGC.ZY^H16;QLGC.Z^H16","isin":"US7472771010","requested_start":"2008-01-02","requested_end":"2011-01-14"},
{"ticker":"RAI","company":"Reynolds American Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"RAI^G17","alternative_rics":"RAI.A^G17;RAI.BAT^G17;RAI.BYX^G17;RAI.B^G17;RAI.C^G17;RAI.DF^G17;RAI.DG^G17;RAI.DY^G17;RAI.EI^G17;RAI.II^G10;RAI.ITC^G17;RAI.MW^G17;RAI.NB^G17;RAI.N^G17;RAI.PH^B09;RAI.PH^G17;RAI.P^G17;RAI.TH^G17;RAI.W^E14;RAI.ZY^G17;RAI.Z^G17","isin":"US7617131062","requested_start":"2008-01-02","requested_end":"2017-07-24"},
{"ticker":"RDC","company":"Rowan Companies Class A Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"RDC^D19","alternative_rics":"RDC.ARC^D19;RDC.A^D19;RDC.BAT^D19;RDC.BT1^D19;RDC.BYX^D19;RDC.B^D19;RDC.C^D19;RDC.DF^D19;RDC.DG^D19;RDC.DY^D19;RDC.EI^D19;RDC.II^G10;RDC.ITC^D19;RDC.MW^D19;RDC.NB^D19;RDC.N^D19;RDC.PH^B09;RDC.PH^D19;RDC.P^D19;RDC.TH^D19;RDC.W^E14;RDC.ZY^D19;RDC.Z^D19","isin":"GB00B6SLMV12","requested_start":"2008-01-02","requested_end":"2014-08-18"},
{"ticker":"RHT","company":"Red Hat Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"RHT^G19","alternative_rics":"RHT.ARC^G19;RHT.A^G19;RHT.BAT^G19;RHT.BT1^G19;RHT.BYX^G19;RHT.B^G19;RHT.C^G19;RHT.DF^G19;RHT.DG^G19;RHT.DY^G19;RHT.EI^G19;RHT.II^G10;RHT.ITC^G19;RHT.MW^G19;RHT.NB^G19;RHT.N^G19;RHT.PH^G19;RHT.P^G19;RHT.TH^G19;RHT.W^E14;RHT.ZY^G19;RHT.Z^G19","isin":"US7565771026","requested_start":"2009-07-27","requested_end":"2019-07-12"},
{"ticker":"ROH","company":"Rohm & Haas Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"ROH.N^D09","alternative_rics":"ROH.B^D09;ROH.C^D09;ROH.DF^D09;ROH.II^D09;ROH.MW^D09;ROH.PH^B09;ROH.P^D09;ROH.TH^D09;ROH.W^D09;ROH.Z^D09;ROH^D09","isin":"US7753711073","requested_start":"2008-01-02","requested_end":"2009-04-01"},
{"ticker":"RRD","company":"RR Donnelley and Sons Ord Shs, Ordinary Share, Delisted, NYSE Arca","ric":"RRD.P^B22","alternative_rics":"RRD.ARC^B22;RRD.A^B22;RRD.A^H14;RRD.BAT^B22;RRD.BT1^B22;RRD.BYX^B22;RRD.B^B22;RRD.C^B22;RRD.DF^B22;RRD.DG^B22;RRD.DY^B22;RRD.EI^B22;RRD.II^G10;RRD.ITC^B22;RRD.LTS^B22;RRD.MEM^B22;RRD.MP^B22;RRD.MW^B22;RRD.NB^B22;RRD.NQT^B22;RRD.N^B22;RRD.PH^B09;RRD.PH^B22;RRD.TH^B22;RRD.TH^H09;RRD.W^E14;RRD.ZY^B22;RRD.Z^B22;RRD^B22","isin":"US2578672006","requested_start":"2008-01-02","requested_end":"2012-12-11"},
{"ticker":"RSHCQ","company":"RS Legacy Ord Shs, Ordinary Share, Delisted, OTC MARKETS GROUP L1 AND L2","ric":"RSHCQ.PK^J15","alternative_rics":"RSHCQ.PQ^J15","isin":"US74979E1010","requested_start":"2008-01-02","requested_end":"2011-06-30"},
{"ticker":"RTN","company":"Raytheon Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"RTN^D20","alternative_rics":"RTN.ARC^D20;RTN.A^D20;RTN.BAT^D20;RTN.BT1^D20;RTN.BYX^D20;RTN.B^D20;RTN.C^D20;RTN.DF^D20;RTN.DG^D20;RTN.DY^D20;RTN.EI^D20;RTN.II^G10;RTN.ITC^D20;RTN.MW^D20;RTN.NB^D20;RTN.N^D20;RTN.PH^B09;RTN.PH^D20;RTN.P^D20;RTN.TH^D20;RTN.W^E14;RTN.ZY^D20;RTN.Z^D20","isin":"US7551115071","requested_start":"2008-01-02","requested_end":"2020-04-03"},
{"ticker":"RX","company":"IMS Health Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"RX^C10","alternative_rics":"RX.B^C10;RX.C^C10;RX.DF^C10;RX.II^C10;RX.MW^C10;RX.N^C10;RX.PH^B09;RX.P^C10;RX.TH^C10;RX.W^C10;RX.Z^C10","isin":"US4499341083","requested_start":"2008-01-02","requested_end":"2010-02-25"},
{"ticker":"SAF","company":"Safeco Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"SAF.N^I08","alternative_rics":"SAF.C^I08;SAF.DF^I08;SAF.II^I08;SAF.MW^I08;SAF.PH^I08;SAF.P^I08;SAF.TH^I08;SAF.W^I08;SAF^I08","isin":"US7864291007","requested_start":"2008-01-02","requested_end":"2008-09-22"},
{"ticker":"SBNY","company":"Signature Bank, Ordinary Share, US 'Other OTC' and Grey Market","ric":"SBNY.PK","alternative_rics":"SBNY.AOI^C23;SBNY.ARC^C23;SBNY.A^C23;SBNY.BAT^C23;SBNY.BT1^C23;SBNY.BYX^C23;SBNY.B^C23;SBNY.C^C23;SBNY.DF^C23;SBNY.DG^C23;SBNY.DY^C23;SBNY.EI^C23;SBNY.GTC;SBNY.ITC^C23;SBNY.LTS^C23;SBNY.MEM^C23;SBNY.MP^C23;SBNY.MW^C23;SBNY.NB^C23;SBNY.NOI^C23;SBNY.NQT^C23;SBNY.N^C23;SBNY.OQ^C23;SBNY.PH^C23;SBNY.PQ;SBNY.P^C23;SBNY.ZY^C23;SBNY.Z^C23","isin":"US82669G1040","requested_start":"2021-12-20","requested_end":"2023-03-14"},
{"ticker":"SCG","company":"SCANA Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"SCG^A19","alternative_rics":"SCG.ARC^A19;SCG.A^A19;SCG.BAT^A19;SCG.BT1^A19;SCG.BYX^A19;SCG.B^A19;SCG.C^A19;SCG.DF^A19;SCG.DG^A19;SCG.DY^A19;SCG.EI^A19;SCG.II^G10;SCG.ITC^A19;SCG.MW^A19;SCG.NB^A19;SCG.N^A19;SCG.PH^A19;SCG.PH^B09;SCG.P^A19;SCG.TH^A19;SCG.W^E14;SCG.ZY^A19;SCG.Z^A19","isin":"US80589M1027","requested_start":"2009-01-02","requested_end":"2018-12-31"},
{"ticker":"SEE","company":"Sealed Air Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"SEE^D26","alternative_rics":"SEE.AOI^D26;SEE.ARC^D26;SEE.A^D26;SEE.BAT^D26;SEE.BLUE^D26;SEE.BT1^D26;SEE.BYX^D26;SEE.B^D26;SEE.C^D26;SEE.DEX^D26;SEE.DF^D26;SEE.DG^D26;SEE.DY^D26;SEE.EI^D26;SEE.II^G10;SEE.ITC^D26;SEE.LTS^D26;SEE.MEM^D26;SEE.MP^D26;SEE.MW^D26;SEE.NB^D26;SEE.NOI^D26;SEE.NQT^D26;SEE.N^D26;SEE.PH^B09;SEE.PH^D26;SEE.P^D26;SEE.TH^D26;SEE.W^E14;SEE.XN^D26;SEE.ZY^D26;SEE.Z^D26","isin":"US81211K1007","requested_start":"2008-01-02","requested_end":"2023-12-15"},
{"ticker":"SHLD","company":"Sears Holdings Ord Shs, Ordinary Share, Delisted, NYSE American when trading NASDAQ Global Select Mkt","ric":"SHLD.A^I12","alternative_rics":"SHLD.A^J18;SHLD.BAT^J18;SHLD.BT1^J18;SHLD.BYX^J18;SHLD.B^J18;SHLD.C^J18;SHLD.DF^J18;SHLD.DG^J18;SHLD.DY^J18;SHLD.EI^J18;SHLD.II^G10;SHLD.ITC^J18;SHLD.MW^J18;SHLD.NB^J18;SHLD.N^J18;SHLD.OQ^J18;SHLD.PH^B09;SHLD.PH^J18;SHLD.P^J18;SHLD.W^E14;SHLD.ZY^J18;SHLD.Z^J18","isin":"US8123501061","requested_start":"2008-01-02","requested_end":"2012-09-04"},
{"ticker":"SIAL","company":"Sigma Aldrich Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"SIAL.O^K15","alternative_rics":"SIAL.A^I12;SIAL.BAT^K15;SIAL.BYX^K15;SIAL.B^K15;SIAL.C^G14;SIAL.DF^K15;SIAL.DG^K15;SIAL.DY^K15;SIAL.II^G10;SIAL.ITC^K15;SIAL.MW^K15;SIAL.NB^K15;SIAL.OQ^K15;SIAL.PH^B09;SIAL.PH^K15;SIAL.P^K15;SIAL.W^E14;SIAL.ZY^K15;SIAL.Z^K15","isin":"US8265521018","requested_start":"2008-01-02","requested_end":"2015-11-17"},
{"ticker":"SIVB","company":"SVB Financial Group Ord Shs, Ordinary Share, Delisted, NYSE AMEX IMBALANCE","ric":"SIVB.AOI^C23","alternative_rics":"SIVB.ARC^C23;SIVB.A^C23;SIVB.BAT^C23;SIVB.BT1^C23;SIVB.BYX^C23;SIVB.B^C23;SIVB.C^C23;SIVB.DF^C23;SIVB.DG^C23;SIVB.DY^C23;SIVB.EI^C23;SIVB.ITC^C23;SIVB.LTS^C23;SIVB.MEM^C23;SIVB.MP^C23;SIVB.MW^C23;SIVB.NB^C23;SIVB.NOI^C23;SIVB.NQT^C23;SIVB.N^C23;SIVB.OQ^C23;SIVB.PH^C23;SIVB.P^C23;SIVB.ZY^C23;SIVB.Z^C23","isin":"US78486Q1013","requested_start":"2018-03-19","requested_end":"2023-03-14"},
{"ticker":"SNI","company":"Scripps Networks Interactive Ord Shs Class A, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"SNI.O^C18","alternative_rics":"SNI.A^C18;SNI.BAT^C18;SNI.BT1^C18;SNI.BYX^C18;SNI.B^C18;SNI.C^C18;SNI.DF^C18;SNI.DG^C18;SNI.DY^C18;SNI.EI^C18;SNI.II^G10;SNI.ITC^C18;SNI.MW^C18;SNI.NB^C18;SNI.OQ^C18;SNI.PH^B09;SNI.PH^C18;SNI.P^C18;SNI.TH^C16;SNI.W^E14;SNI.ZY^C18;SNI.Z^C18","isin":"US8110651010","requested_start":"2008-07-01","requested_end":"2018-03-06"},
{"ticker":"SOV","company":"Santander Holdings Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"SOV.N^A09","alternative_rics":"SOV.B^A09;SOV.C^A09;SOV.DF^A09;SOV.II^A09;SOV.MW^A09;SOV.PH^A09;SOV.P^A09;SOV.TH^A09;SOV.W^A09;SOV.Z^A09;SOV^A09","isin":"US8459051087","requested_start":"2008-01-02","requested_end":"2009-01-29"},
{"ticker":"SPLS","company":"Staples Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"SPLS.O^I17","alternative_rics":"SPLS.A^I17;SPLS.BAT^I17;SPLS.BYX^I17;SPLS.B^I17;SPLS.C^I17;SPLS.DF^I17;SPLS.DG^I17;SPLS.DY^I17;SPLS.EI^I17;SPLS.II^G10;SPLS.ITC^I17;SPLS.MW^I17;SPLS.NB^I17;SPLS.OQ^I17;SPLS.PH^B09;SPLS.PH^I17;SPLS.P^I17;SPLS.W^E14;SPLS.ZY^I17;SPLS.Z^I17","isin":"US8550301027","requested_start":"2008-01-02","requested_end":"2017-09-12"},
{"ticker":"SRCL","company":"Stericycle Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"SRCL.O^K24","alternative_rics":"SRCL.AOI^K24;SRCL.ARC^K24;SRCL.A^I12;SRCL.A^K24;SRCL.BAT^K24;SRCL.BT1^K24;SRCL.BYX^K24;SRCL.B^K24;SRCL.C^K24;SRCL.DEX^K24;SRCL.DF^K24;SRCL.DG^K24;SRCL.DY^K24;SRCL.EI^K24;SRCL.II^G10;SRCL.ITC^K24;SRCL.LTS^K24;SRCL.MEM^K24;SRCL.MP^K24;SRCL.MW^K24;SRCL.NB^K24;SRCL.NOI^K24;SRCL.NQT^K24;SRCL.N^K24;SRCL.OQ^K24;SRCL.PH^B09;SRCL.PH^K24;SRCL.P^K24;SRCL.W^E14;SRCL.ZY^K24;SRCL.Z^K24","isin":"US8589121081","requested_start":"2008-11-19","requested_end":"2018-11-30"},
{"ticker":"STJ","company":"St Jude Medical Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"STJ^A17","alternative_rics":"STJ.BAT^A17;STJ.BYX^A17;STJ.B^A17;STJ.C^A17;STJ.DF^A17;STJ.DG^A17;STJ.DY^A17;STJ.EI^A17;STJ.II^G10;STJ.ITC^A17;STJ.MW^A17;STJ.NB^A17;STJ.N^A17;STJ.PH^A17;STJ.PH^B09;STJ.P^A17;STJ.TH^A17;STJ.W^E14;STJ.ZY^A17;STJ.Z^A17","isin":"US7908491035","requested_start":"2008-01-02","requested_end":"2017-01-04"},
{"ticker":"SUN","company":"Sunoco Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"SUN^J12","alternative_rics":"SUN.B^J12;SUN.C^J12;SUN.DF^J12;SUN.DG^J12;SUN.DY^J12;SUN.II^G10;SUN.MW^J12;SUN.N^J12;SUN.PH^B09;SUN.PH^J12;SUN.P^J12;SUN.TH^J12;SUN.W^J12;SUN.ZY^J12;SUN.Z^J12","isin":"US86764P1093","requested_start":"2008-01-02","requested_end":"2012-10-04"},
{"ticker":"SUNEQ","company":"SunEdison Ord Shs, Ordinary Share, Delisted, OTC MARKETS GROUP L1 AND L2","ric":"SUNEQ.PK^L17","alternative_rics":"SUNEQ.PQ^L17","isin":"US86732Y1091","requested_start":"2008-01-02","requested_end":"2011-12-16"},
{"ticker":"SWN","company":"Southwestern Energy Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"SWN^J24","alternative_rics":"SWN.AOI^J24;SWN.ARC^J24;SWN.A^J24;SWN.BAT^J24;SWN.BT1^J24;SWN.BYX^J24;SWN.B^J24;SWN.C^J24;SWN.DEX^J24;SWN.DF^J24;SWN.DG^J24;SWN.DY^J24;SWN.EI^J24;SWN.II^G10;SWN.ITC^J24;SWN.LTS^J24;SWN.MEM^J24;SWN.MP^J24;SWN.MW^J24;SWN.NB^J24;SWN.NOI^J24;SWN.NQT^J24;SWN.N^J24;SWN.PH^B09;SWN.PH^J24;SWN.P^J24;SWN.TH^J24;SWN.W^E14;SWN.ZY^J24;SWN.Z^J24","isin":"US8454671095","requested_start":"2008-06-06","requested_end":"2017-04-03"},
{"ticker":"SWY","company":"Safeway Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"SWY^A15","alternative_rics":"SWY.BAT^A15;SWY.BYX^A15;SWY.B^A15;SWY.C^G14;SWY.DF^A15;SWY.DG^A15;SWY.DY^A15;SWY.II^G10;SWY.ITC^A15;SWY.MW^A15;SWY.NB^A15;SWY.N^A15;SWY.PH^A15;SWY.PH^B09;SWY.P^A15;SWY.TH^A15;SWY.W^E14;SWY.ZY^A15;SWY.Z^A15","isin":"US7865142084","requested_start":"2008-01-02","requested_end":"2015-01-26"},
{"ticker":"TEG","company":"Integrys Energy Group Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"TEG^F15","alternative_rics":"TEG.BAT^F15;TEG.BYX^F15;TEG.B^F15;TEG.C^G14;TEG.DF^F15;TEG.DG^F15;TEG.DY^F15;TEG.II^G10;TEG.ITC^F15;TEG.MW^F15;TEG.NB^F15;TEG.N^F15;TEG.PH^B09;TEG.PH^F15;TEG.P^F15;TEG.TH^F15;TEG.W^E14;TEG.ZY^F15;TEG.Z^F15","isin":"US45822P1057","requested_start":"2008-01-02","requested_end":"2015-06-29"},
{"ticker":"TGNA","company":"Tegna Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"TGNA.K^C26","alternative_rics":"TGNA.AOI^C26;TGNA.ARC^C26;TGNA.A^C26;TGNA.BAT^C26;TGNA.BLUE^C26;TGNA.BT1^C26;TGNA.BYX^C26;TGNA.B^C26;TGNA.C^C26;TGNA.DEX^C26;TGNA.DF^C26;TGNA.DG^C26;TGNA.DY^C26;TGNA.EI^C26;TGNA.ITC^C26;TGNA.LTS^C26;TGNA.MEM^C26;TGNA.MP^C26;TGNA.MW^C26;TGNA.NB^C26;TGNA.NOI^C26;TGNA.NQT^C26;TGNA.N^C26;TGNA.PH^C26;TGNA.P^C26;TGNA.TH^C26;TGNA.XN^C26;TGNA.ZY^C26;TGNA.Z^C26","isin":"US87901J1051","requested_start":"2008-01-02","requested_end":"2017-06-01"},
{"ticker":"TIE","company":"Titanium Metals Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"TIE^A13","alternative_rics":"TIE.B^A13;TIE.C^A13;TIE.DF^A13;TIE.DG^A13;TIE.DY^A13;TIE.II^G10;TIE.MW^A13;TIE.N^A13;TIE.PH^A13;TIE.PH^B09;TIE.P^A13;TIE.TH^A13;TIE.W^A13;TIE.ZY^A13;TIE.Z^A13","isin":"US8883392073","requested_start":"2008-01-02","requested_end":"2012-12-21"},
{"ticker":"TIF","company":"Tiffany Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"TIF^A21","alternative_rics":"TIF.ARC^A21;TIF.A^A21;TIF.BAT^A21;TIF.BT1^A21;TIF.BYX^A21;TIF.B^A21;TIF.C^A21;TIF.DF^A21;TIF.DG^A21;TIF.DY^A21;TIF.EI^A21;TIF.II^G10;TIF.ITC^A21;TIF.LTS^A21;TIF.MEM^A21;TIF.MP^A21;TIF.MW^A21;TIF.NB^A21;TIF.N^A21;TIF.PH^A21;TIF.PH^B09;TIF.P^A21;TIF.TH^A21;TIF.W^E14;TIF.ZY^A21;TIF.Z^A21","isin":"US8865471085","requested_start":"2008-01-02","requested_end":"2021-01-06"},
{"ticker":"TSS","company":"Total System Services Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"TSS^I19","alternative_rics":"TSS.ARC^I19;TSS.A^I19;TSS.BAT^I19;TSS.BT1^I19;TSS.BYX^I19;TSS.B^I19;TSS.C^I19;TSS.DF^I19;TSS.DG^I19;TSS.DY^I19;TSS.EI^I19;TSS.II^G10;TSS.ITC^I19;TSS.MW^I19;TSS.NB^I19;TSS.N^I19;TSS.PH^B09;TSS.PH^I19;TSS.P^I19;TSS.TH^I19;TSS.W^E14;TSS.ZY^I19;TSS.Z^I19","isin":"US8919061098","requested_start":"2008-01-02","requested_end":"2019-09-20"},
{"ticker":"TWC","company":"Time Warner Cable Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"TWC^E16","alternative_rics":"TWC.BAT^E16;TWC.BYX^E16;TWC.B^E16;TWC.C^E16;TWC.DF^E16;TWC.DG^E16;TWC.DY^E16;TWC.II^G10;TWC.ITC^E16;TWC.MW^E16;TWC.NB^E16;TWC.N^E16;TWC.PH^E16;TWC.P^E16;TWC.TH^E16;TWC.W^E14;TWC.ZY^E16;TWC.Z^E16","isin":"US88732J2078","requested_start":"2009-03-30","requested_end":"2016-05-17"},
{"ticker":"TWTR","company":"Twitter Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"TWTR.K^J22","alternative_rics":"TWTR.AOI^J22;TWTR.ARC^J22;TWTR.A^J22;TWTR.BAT^J22;TWTR.BT1^J22;TWTR.BYX^J22;TWTR.B^J22;TWTR.C^J22;TWTR.DF^J22;TWTR.DG^J22;TWTR.DY^J22;TWTR.EI^J22;TWTR.ITC^J22;TWTR.LTS^J22;TWTR.MEM^J22;TWTR.MP^J22;TWTR.MW^J22;TWTR.NB^J22;TWTR.NOI^J22;TWTR.NQT^J22;TWTR.N^J22;TWTR.PH^J22;TWTR.P^J22;TWTR.TH^J22;TWTR.ZY^J22;TWTR.Z^J22","isin":"US90184L1026","requested_start":"2018-06-07","requested_end":"2022-10-31"},
{"ticker":"TWX","company":"Time Warner Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"TWX^F18","alternative_rics":"TWX.A^F18;TWX.BAT^F18;TWX.BT1^F18;TWX.BYX^F18;TWX.B^F18;TWX.C^F18;TWX.DF^F18;TWX.DG^F18;TWX.DY^F18;TWX.EI^F18;TWX.II^G10;TWX.ITC^F18;TWX.MW^F18;TWX.NB^F18;TWX.N^F18;TWX.PH^B09;TWX.PH^F18;TWX.P^F18;TWX.TH^F18;TWX.W^E14;TWX.ZY^F18;TWX.Z^F18","isin":"US8873173038","requested_start":"2008-01-02","requested_end":"2018-06-14"},
{"ticker":"UST","company":"UST Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"UST.N^A09","alternative_rics":"UST.C^A09;UST.DF^A09;UST.II^A09;UST.MW^A09;UST.PH^A09;UST.P^A09;UST.TH^A09;UST.W^A09;UST.Z^A09;UST^A09","isin":"US9029111062","requested_start":"2008-01-02","requested_end":"2009-01-05"},
{"ticker":"UTX","company":"RTX Ord Shs, Ordinary Share, Delisted, ISE when trading NYSE and AMEX Stocks","ric":"UTX.II^G10","alternative_rics":"UTX.PH^B09;UTX.W^E14","isin":"US75513E1010","requested_start":"2008-01-02","requested_end":"2020-04-02"},
{"ticker":"VAR","company":"Varian Medical Systems Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"VAR^D21","alternative_rics":"VAR.ARC^D21;VAR.A^D21;VAR.BAT^D21;VAR.BT1^D21;VAR.BYX^D21;VAR.B^D21;VAR.C^D21;VAR.DF^D21;VAR.DG^D21;VAR.DY^D21;VAR.EI^D21;VAR.II^G10;VAR.ITC^D21;VAR.LTS^D21;VAR.MEM^D21;VAR.MP^D21;VAR.MW^D21;VAR.NB^D21;VAR.N^D21;VAR.PH^B09;VAR.PH^D21;VAR.P^D21;VAR.TH^D21;VAR.W^E14;VAR.ZY^D21;VAR.Z^D21","isin":"US92220P1057","requested_start":"2008-01-02","requested_end":"2021-04-19"},
{"ticker":"VIAB","company":"Viacom Ord Shs Class B, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"VIAB.O^L19","alternative_rics":"VIAB.ARC^L19;VIAB.A^L19;VIAB.BAT^L19;VIAB.BT1^L19;VIAB.BYX^L19;VIAB.B^L19;VIAB.C^L19;VIAB.DF^L19;VIAB.DG^L19;VIAB.DY^L19;VIAB.EI^L19;VIAB.ITC^L19;VIAB.MW^L19;VIAB.NB^L19;VIAB.N^L19;VIAB.OQ^L19;VIAB.PH^L19;VIAB.P^L19;VIAB.W^E14;VIAB.ZY^L19;VIAB.Z^L19;VIAb.II^G10;VIAb.PH^B09;VIAb.TH^L11","isin":"US92553P2011","requested_start":"2008-01-02","requested_end":"2019-12-04"},
{"ticker":"VLTO","company":"Veralto Corporation, Ordinary Share, NYSE Consolidated","ric":"VLTO.K","alternative_rics":"VLTO.A;VLTO.AOI;VLTO.ARC;VLTO.B;VLTO.BAT;VLTO.BLUE;VLTO.BT1;VLTO.BYX;VLTO.C;VLTO.DEX;VLTO.DF;VLTO.DG;VLTO.DY;VLTO.EI;VLTO.ITC;VLTO.LTS;VLTO.MEM;VLTO.MP;VLTO.MW;VLTO.N;VLTO.NB;VLTO.NIB;VLTO.NOI;VLTO.NQT;VLTO.P;VLTO.PH;VLTO.TH;VLTO.TXS;VLTO.XN;VLTO.Z;VLTO.ZY","isin":"US92338C1036","requested_start":"2023-10-02","requested_end":"2026-08-18"},
{"ticker":"WAMUQ","company":"Washington Mutual Ord Shs, Ordinary Share, Delisted, OTC Markets Group Inc - Limited Information","ric":"WAMUQ.PK^C12","alternative_rics":"","isin":"US9393221034","requested_start":"2008-01-02","requested_end":"2008-09-29"},
{"ticker":"WBA","company":"Walgreen Boots Alliance Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"WBA.O^H25","alternative_rics":"WBA.AOI^H25;WBA.ARC^H25;WBA.A^H25;WBA.BAT^H25;WBA.BLUE^H25;WBA.BT1^H25;WBA.BYX^H25;WBA.B^H25;WBA.C^H25;WBA.DEX^H25;WBA.DF^H25;WBA.DG^H25;WBA.DY^H25;WBA.EI^H25;WBA.ITC^H25;WBA.LTS^H25;WBA.MEM^H25;WBA.MP^H25;WBA.MW^H25;WBA.NB^H25;WBA.NOI^H25;WBA.NQT^H25;WBA.N^H25;WBA.OQ^H25;WBA.PH^H25;WBA.P^H25;WBA.ZY^H25;WBA.Z^H25","isin":"US9314271084","requested_start":"2008-01-02","requested_end":"2025-08-27"},
{"ticker":"WCG","company":"Wellcare Healthcare Plans Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"WCG^A20","alternative_rics":"WCG.ARC^A20;WCG.A^A20;WCG.BAT^A20;WCG.BT1^A20;WCG.BYX^A20;WCG.B^A20;WCG.C^A20;WCG.DF^A20;WCG.DG^A20;WCG.DY^A20;WCG.EI^A20;WCG.ITC^A20;WCG.MW^A20;WCG.NB^A20;WCG.N^A20;WCG.PH^A20;WCG.P^A20;WCG.TH^A20;WCG.ZY^A20;WCG.Z^A20","isin":"US94946T1060","requested_start":"2018-09-17","requested_end":"2020-01-27"},
{"ticker":"WFM","company":"Whole Foods Market Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"WFM.O^H17","alternative_rics":"WFM.A^H17;WFM.A^I12;WFM.BAT^H17;WFM.BYX^H17;WFM.B^H17;WFM.C^H17;WFM.DF^H17;WFM.DG^H17;WFM.DY^H17;WFM.EI^H17;WFM.ITC^H17;WFM.MW^H17;WFM.NB^H17;WFM.OQ^H17;WFM.PH^H17;WFM.P^H17;WFM.W^E14;WFM.ZY^H17;WFM.Z^H17","isin":"US9668371068","requested_start":"2008-01-02","requested_end":"2017-08-25"},
{"ticker":"WFT","company":"Weatherford International Ord Shs, Ordinary Share, Delisted, NYSE ArcaBook Equities","ric":"WFT.ARC^E19","alternative_rics":"WFT.A^E19;WFT.BAT^E19;WFT.BT1^E19;WFT.BYX^E19;WFT.B^E19;WFT.C^E19;WFT.DF^E19;WFT.DG^E19;WFT.DY^E19;WFT.EI^E19;WFT.II^G10;WFT.ITC^E19;WFT.MW^E19;WFT.NB^E19;WFT.N^E19;WFT.PH^B09;WFT.PH^E19;WFT.P^E19;WFT.TH^E19;WFT.W^E14;WFT.ZY^E19;WFT.Z^E19","isin":"IE00BLNN3691","requested_start":"2008-01-02","requested_end":"2009-02-25"},
{"ticker":"WIN","company":"Windstream Holdings Ord Shs, Ordinary Share, Delisted, NYSE ArcaBook Equities","ric":"WIN.ARC^C19","alternative_rics":"WIN.A^C19;WIN.BAT^C19;WIN.BT1^C19;WIN.BYX^C19;WIN.B^C19;WIN.C^C19;WIN.DF^C19;WIN.DG^C19;WIN.DY^C19;WIN.EI^C19;WIN.II^G10;WIN.ITC^C19;WIN.MW^C19;WIN.NB^C19;WIN.N^C19;WIN.OQ^C19;WIN.PH^B09;WIN.PH^C19;WIN.P^C19;WIN.TH^L09;WIN.W^E14;WIN.ZY^C19;WIN.Z^C19","isin":"US97382A3095","requested_start":"2008-01-02","requested_end":"2015-04-06"},
{"ticker":"WPX","company":"WPX Energy Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"WPX^A21","alternative_rics":"WPX.ARC^A21;WPX.A^A21;WPX.BAT^A21;WPX.BT1^A21;WPX.BYX^A21;WPX.B^A21;WPX.C^A21;WPX.DF^A21;WPX.DG^A21;WPX.DY^A21;WPX.EI^A21;WPX.ITC^A21;WPX.LTS^A21;WPX.MEM^A21;WPX.MP^A21;WPX.MW^A21;WPX.NB^A21;WPX.N^A21;WPX.PH^A21;WPX.P^A21;WPX.TH^A21;WPX.W^E14;WPX.ZY^A21;WPX.Z^A21","isin":"US98212B1035","requested_start":"2012-01-03","requested_end":"2014-03-21"},
{"ticker":"WRK","company":"Westrock Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"WRK^G24","alternative_rics":"WRK.AOI^G24;WRK.ARC^G24;WRK.A^G24;WRK.BAT^G24;WRK.BT1^G24;WRK.BYX^G24;WRK.B^G24;WRK.C^G24;WRK.DEX^G24;WRK.DF^G24;WRK.DG^G24;WRK.DY^G24;WRK.EI^G24;WRK.ITC^G24;WRK.LTS^G24;WRK.MEM^G24;WRK.MP^G24;WRK.MW^G24;WRK.NB^G24;WRK.NOI^G24;WRK.NQT^G24;WRK.N^G24;WRK.PH^G24;WRK.P^G24;WRK.TH^G24;WRK.ZY^G24;WRK.Z^G24","isin":"US96145D1054","requested_start":"2015-07-02","requested_end":"2024-07-05"},
{"ticker":"WWY","company":"WM Wrigley Jr Ord Shs, Ordinary Share, Delisted, New York Stock Exchange","ric":"WWY.N^J08","alternative_rics":"WWY.C^J08;WWY.DF^J08;WWY.II^J08;WWY.MW^J08;WWY.PH^J08;WWY.P^J08;WWY.TH^J08;WWY.W^J08;WWY^J08","isin":"US9825261053","requested_start":"2008-01-02","requested_end":"2008-10-06"},
{"ticker":"WYE","company":"Wyeth Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"WYE^J09","alternative_rics":"WYE.B^J09;WYE.C^J09;WYE.DF^J09;WYE.II^J09;WYE.MW^J09;WYE.N^J09;WYE.PH^B09;WYE.P^J09;WYE.TH^J09;WYE.W^J09;WYE.Z^J09","isin":"US9830241009","requested_start":"2008-01-02","requested_end":"2009-10-15"},
{"ticker":"X","company":"US Steel Corp Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"X^F25","alternative_rics":"X.AOI^F25;X.ARC^F25;X.A^F25;X.BAT^F25;X.BLUE^F25;X.BT1^F25;X.BYX^F25;X.B^F25;X.C^F25;X.DEX^F25;X.DF^F25;X.DG^F25;X.DY^F25;X.EI^F25;X.II^G10;X.ITC^F25;X.LTS^F25;X.MEM^F25;X.MP^F25;X.MW^F25;X.NB^F25;X.NOI^F25;X.NQT^F25;X.N^F25;X.PH^B09;X.PH^F25;X.P^F25;X.TH^F25;X.W^E14;X.ZY^F25;X.Z^F25","isin":"US9129091081","requested_start":"2008-01-02","requested_end":"2014-07-01"},
{"ticker":"XEC","company":"Cimarex Energy Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"XEC^J21","alternative_rics":"XEC.ARC^J21;XEC.A^J21;XEC.BAT^J21;XEC.BT1^J21;XEC.BYX^J21;XEC.B^J21;XEC.C^J21;XEC.DF^J21;XEC.DG^J21;XEC.DY^J21;XEC.EI^J21;XEC.ITC^J21;XEC.LTS^J21;XEC.MEM^J21;XEC.MP^J21;XEC.MW^J21;XEC.NB^J21;XEC.NQT^J21;XEC.N^J21;XEC.PH^J21;XEC.P^J21;XEC.TH^J21;XEC.ZY^J21;XEC.Z^J21","isin":"US1717981013","requested_start":"2014-06-20","requested_end":"2020-03-02"},
{"ticker":"XL","company":"XL Group Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"XL^I18","alternative_rics":"XL.A^I18;XL.BAT^I18;XL.BT1^I18;XL.BYX^I18;XL.B^I18;XL.C^I18;XL.DF^I18;XL.DG^I18;XL.DY^I18;XL.EI^I18;XL.II^G10;XL.ITC^I18;XL.MW^I18;XL.NB^I18;XL.N^I18;XL.PH^B09;XL.PH^I18;XL.P^I18;XL.TH^I18;XL.W^E14;XL.ZY^I18;XL.Z^I18","isin":"BMG982941046","requested_start":"2008-01-02","requested_end":"2018-09-11"},
{"ticker":"XLNX","company":"Xilinx Ord Shs, Ordinary Share, Delisted, NASDAQ Global Select Consolidated","ric":"XLNX.O^B22","alternative_rics":"XLNX.ARC^B22;XLNX.A^B22;XLNX.A^I12;XLNX.A^J16;XLNX.BAT^B22;XLNX.BT1^B22;XLNX.BYX^B22;XLNX.B^B22;XLNX.C^B22;XLNX.DF^B22;XLNX.DG^B22;XLNX.DY^B22;XLNX.EI^B22;XLNX.II^G10;XLNX.ITC^B22;XLNX.LTS^B22;XLNX.MEM^B22;XLNX.MP^B22;XLNX.MW^B22;XLNX.NB^B22;XLNX.NQT^B22;XLNX.N^B22;XLNX.OQ^B22;XLNX.PH^B09;XLNX.PH^B22;XLNX.P^B22;XLNX.W^E14;XLNX.ZY^B22;XLNX.Z^B22","isin":"US9839191015","requested_start":"2008-01-02","requested_end":"2022-02-14"},
{"ticker":"XTO","company":"XTO Energy Ord Shs, Ordinary Share, Delisted, NYSE Consolidated","ric":"XTO^F10","alternative_rics":"XTO.B^F10;XTO.C^F10;XTO.DF^F10;XTO.II^F10;XTO.MW^F10;XTO.N^F10;XTO.PH^B09;XTO.P^F10;XTO.TH^F10;XTO.W^F10;XTO.Z^F10","isin":"US98385X1063","requested_start":"2008-01-02","requested_end":"2010-06-25"}]
'''

RAW_FIELDS = ['OPEN_PRC', 'HIGH_1', 'LOW_1', 'TRDPRC_1', 'ACVOL_UNS']
ADJUSTMENTS = ['exchangeCorrection', 'manualCorrection', 'CCH', 'CRE', 'RPO', 'RTS']
KINDS = ['unadjusted_ohlcv', 'corporate_adjusted_close', 'daily_total_return']
FIELD_NAMES = {
    'OPEN_PRC': 'open_unadjusted', 'HIGH_1': 'high_unadjusted',
    'LOW_1': 'low_unadjusted', 'TRDPRC_1': 'close_unadjusted',
    'ACVOL_UNS': 'volume_unadjusted',
}


def clean_name(text):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', text)


def column_parts(column):
    return [str(part).strip().casefold() for part in
            (column if isinstance(column, tuple) else (column,))]


def find_column(frame, names):
    wanted = {name.casefold() for name in names}
    matches = [col for col in frame.columns if wanted.intersection(column_parts(col))]
    if len(matches) != 1:
        raise ValueError(f'Expected one column from {names}; found {matches}; headers={list(frame.columns)}')
    return matches[0]


def dates(values):
    return pd.to_datetime(values, errors='coerce', utc=True).tz_convert(None).normalize()


def finish_series(series, start, end):
    series = series.loc[series.index.notna()].sort_index()
    series = series.loc[(series.index >= pd.Timestamp(start)) &
                        (series.index <= pd.Timestamp(end))]
    for _, group in series.groupby(level=0):
        if group.dropna().nunique() > 1:
            raise ValueError('Conflicting values for the same actual observation date')
    # Do not average conflicting dates; identical repeated provider values are safe to collapse.
    series = series.groupby(level=0).first()
    series.index.name = 'date'
    return series


def parse_history(frame, kind, start, end):
    expected = list(FIELD_NAMES.values()) if kind == 'unadjusted_ohlcv' else ['close_lseg_corporate_adjusted']
    if frame is None or frame.empty:
        return pd.DataFrame(columns=expected, index=pd.DatetimeIndex([], name='date'))
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError(f'Expected trading-date index, got {type(frame.index).__name__}')
    index = dates(frame.index)
    fields = FIELD_NAMES if kind == 'unadjusted_ohlcv' else {'TRDPRC_1': expected[0]}
    result = {}
    for field, label in fields.items():
        # Missing individual OHLCV fields remain explicitly unavailable.
        matches = [col for col in frame.columns if field.casefold() in column_parts(col)]
        if not matches:
            result[label] = pd.Series(float('nan'), index=index)
        else:
            col = find_column(frame, [field])
            result[label] = pd.Series(pd.to_numeric(frame[col], errors='coerce').to_numpy(), index=index)
    return pd.DataFrame({label: finish_series(series, start, end)
                         for label, series in result.items()})


def parse_total_return(frame, start, end):
    name = 'total_return_1d_provider_value'
    if frame is None or frame.empty:
        return pd.DataFrame(columns=[name], index=pd.DatetimeIndex([], name='date'))
    date_column = find_column(frame, ['TR.TotalReturn1D.date'])
    value_column = find_column(frame, ['TR.TotalReturn1D'])
    # The field's actual observation date avoids carrying the last return into non-trading days.
    index = dates(pd.DatetimeIndex(frame[date_column]))
    series = pd.Series(pd.to_numeric(frame[value_column], errors='coerce').to_numpy(), index=index)
    return finish_series(series, start, end).to_frame(name)


def chunks():
    start = pd.Timestamp(START_DATE)
    end = pd.Timestamp(END_DATE)
    while start <= end:
        stop = min(start + pd.DateOffset(years=CHUNK_YEARS) - pd.Timedelta(days=1), end)
        yield str(start.date()), str(stop.date())
        start = stop + pd.Timedelta(days=1)


def name_headers(function):
    parameters = inspect.signature(function).parameters
    if 'header_type' in parameters:
        return {'header_type': ld.HeaderType.NAME}
    if 'use_field_names_in_headers' in parameters:
        return {'use_field_names_in_headers': True}
    return {}


def request_frame(ric, kind, start, end):
    if kind == 'reference':
        return ld.get_data(
            universe=[ric], fields=['TR.ISIN', 'TR.CommonName', 'TR.PriceClose.Currency'],
            **name_headers(ld.get_data),
        )
    if kind == 'daily_total_return':
        return ld.get_data(
            universe=[ric], fields=['TR.TotalReturn1D.date', 'TR.TotalReturn1D'],
            parameters={'SDate': start, 'EDate': end, 'Frq': 'D'},
            **name_headers(ld.get_data),
        )
    return ld.get_history(
        universe=ric, fields=RAW_FIELDS if kind == 'unadjusted_ohlcv' else ['TRDPRC_1'],
        interval='1D', start=start, end=end, count=10000,
        adjustments='unadjusted' if kind == 'unadjusted_ohlcv' else ADJUSTMENTS,
        **name_headers(ld.get_history),
    )


def save_raw(frame, path):
    # Preserve values, actual date labels and all header levels without assuming their order.
    payload = {
        'datetime_index': isinstance(frame.index, pd.DatetimeIndex),
        'multi_columns': isinstance(frame.columns, pd.MultiIndex),
        'table': json.loads(frame.to_json(orient='split', date_format='iso')),
    }
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def read_raw(path):
    payload = json.loads(path.read_text(encoding='utf-8'))
    table = payload['table']
    columns = (pd.MultiIndex.from_tuples([tuple(col) for col in table['columns']])
               if payload['multi_columns'] else table['columns'])
    index = pd.to_datetime(table['index'], utc=True) if payload['datetime_index'] else table['index']
    return pd.DataFrame(table['data'], index=index, columns=columns)


def fetch_chunk(item, kind, start, end, events):
    directory = OUTPUT_DIR / 'Raw' / clean_name(item['ticker'])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{kind}_{start}_{end}.json'
    if path.exists():
        try:
            frame = read_raw(path)
            if not frame.empty:
                return frame
        except (ValueError, KeyError, TypeError):
            events.append(f'{kind} {start}: unreadable cache; requesting again')
    for attempt in range(1, ATTEMPTS + 1):
        try:
            frame = request_frame(item['ric'], kind, start, end)
            if frame is None:
                frame = pd.DataFrame()
            if not isinstance(frame, pd.DataFrame):
                raise TypeError(f'LSEG returned {type(frame).__name__}, expected DataFrame')
            save_raw(frame, path)
            # Retry empty results once; no-price periods can also be legitimate.
            if frame.empty and attempt < ATTEMPTS:
                continue
            return frame
        except Exception as error:
            if attempt == ATTEMPTS:
                events.append(f'{kind} {start}..{end}: {type(error).__name__}: {error}')
                return pd.DataFrame()
        finally:
            time.sleep(PAUSE_SECONDS)


def combine(frames):
    if not frames:
        return pd.DataFrame(index=pd.DatetimeIndex([], name='date'))
    result = pd.concat(frames).sort_index()
    if result.index.duplicated().any():
        raise ValueError('Overlapping observation dates between non-overlapping request chunks')
    return result


def download_security(item):
    events = []
    reference = fetch_chunk(item, 'reference', START_DATE, END_DATE, events)
    metadata = {}
    for label, field in [('reference_isin', 'TR.ISIN'), ('reference_company', 'TR.CommonName'),
                         ('reference_currency', 'TR.PriceClose.Currency')]:
        try:
            values = reference[find_column(reference, [field])].dropna().astype(str).unique()
            metadata[label] = ';'.join(values)
        except ValueError:
            metadata[label] = ''
    reference_isin = metadata['reference_isin']
    identity = ('mismatch_review_required' if reference_isin and reference_isin != item['isin']
                else 'isin_agrees_identity_still_unverified' if reference_isin
                else 'reference_identity_unavailable')
    by_kind = {kind: [] for kind in KINDS}
    for start, end in chunks():
        for kind in KINDS:
            raw = fetch_chunk(item, kind, start, end, events)
            try:
                parsed = (parse_total_return(raw, start, end) if kind == 'daily_total_return'
                          else parse_history(raw, kind, start, end))
                by_kind[kind].append(parsed)
            except Exception as error:
                events.append(f'{kind} {start}: parse error: {error}; original response retained in Raw')
    frames = {kind: combine(parts) for kind, parts in by_kind.items()}
    panel = pd.concat(list(frames.values()), axis=1).sort_index()
    numeric = list(FIELD_NAMES.values()) + ['close_lseg_corporate_adjusted', 'total_return_1d_provider_value']
    panel = panel.reindex(columns=numeric).dropna(how='all')
    # Values are preserved, including suspicious/negative values; diagnostics do not clean them.
    for column, value in [('ticker', item['ticker']), ('ric', item['ric']),
                          ('isin', item['isin']), ('company', item['company'])]:
        panel[column] = value
    panel['has_observed_positive_raw_close'] = panel['close_unadjusted'].gt(0)
    panel['mapping_verified'] = False
    panel['reference_currency'] = metadata['reference_currency']
    panel.index.name = 'date'
    data_path = OUTPUT_DIR / 'Datasets' / f"{clean_name(item['ticker'])}.csv"
    temporary = data_path.with_suffix('.tmp')
    panel.to_csv(temporary, encoding='utf-8-sig')
    temporary.replace(data_path)
    counts = {col: int(panel[col].notna().sum()) for col in numeric}
    price_dates = panel.index[panel['close_unadjusted'].gt(0)]
    original_dates = panel.index[(panel.index >= pd.Timestamp(item['requested_start'])) &
                                 (panel.index <= pd.Timestamp(item['requested_end'])) &
                                 panel['close_unadjusted'].gt(0)]
    if identity == 'mismatch_review_required':
        status = 'IDENTITY_MISMATCH_REVIEW'
    elif not counts['close_unadjusted'] and not counts['close_lseg_corporate_adjusted']:
        status = 'NO_PRICE_DATA'
    elif events or not all(counts.get(col, 0) for col in
                           ['close_unadjusted', 'volume_unadjusted',
                            'close_lseg_corporate_adjusted', 'total_return_1d_provider_value']):
        status = 'PARTIAL_DOWNLOAD'
    else:
        status = 'DOWNLOADED_CANDIDATE'
    return {
        'ticker': item['ticker'], 'company': item['company'], 'ric': item['ric'],
        'isin': item['isin'], 'status': status, 'mapping_verified': False,
        **metadata, 'reference_identity_check': identity,
        'download_start': START_DATE, 'download_end': END_DATE,
        'membership_start': item['requested_start'], 'membership_end': item['requested_end'],
        'first_positive_raw_close': str(price_dates.min().date()) if len(price_dates) else '',
        'last_positive_raw_close': str(price_dates.max().date()) if len(price_dates) else '',
        'raw_price_dates_between_membership_bounds': len(original_dates),
        'nonpositive_raw_prices': int(panel['close_unadjusted'].le(0).sum()),
        'negative_volumes': int(panel['volume_unadjusted'].lt(0).sum()),
        'total_return_values_without_positive_raw_close': int(
            (panel['total_return_1d_provider_value'].notna() & ~panel['has_observed_positive_raw_close']).sum()),
        **{f'{col}_observations': count for col, count in counts.items()},
        'event_count': len(events), 'events': ' | '.join(events),
        'data_file': str(data_path.relative_to(OUTPUT_DIR)),
    }


DESCRIPTION = '''# LSEG recovery download — candidate histories

This is a separate acquisition bundle, not an approved replacement for Yahoo data.
209 unique single_security_review candidates are frozen from the supplied mapping CSV.
The script requests the full 2008-01-01 to 2026-08-18 period for warm-up, membership,
post-membership outcomes, and overlap comparisons. IPOs/delistings naturally shorten it.
No currency conversion, forward fill, price clipping, rebasing or Yahoo splicing is done.

## Files
- download_report.csv: ONE report, one row per candidate, rewritten after each ticker.
- Datasets/TICKER.csv: dated values with original ticker, RIC, company and ISIN.
- Raw/TICKER/*.json: original response tables, including dates/headers, per request chunk.
- run_metadata.json: source mapping, exact parameters and field descriptions.

## Columns
- open/high/low/close_unadjusted: OPEN_PRC/HIGH_1/LOW_1/TRDPRC_1 with adjustments=unadjusted.
- volume_unadjusted: ACVOL_UNS in the same unadjusted pricing request.
- close_lseg_corporate_adjusted: TRDPRC_1 with exchangeCorrection, manualCorrection,
  CCH, CRE, RPO and RTS. This is NOT automatically equivalent to Yahoo Adj Close.
- total_return_1d_provider_value: TR.TotalReturn1D, preserved without scaling. Confirm
  field units in Workspace DIB before converting to decimal returns (normally percent).
  Dates use TR.TotalReturn1D.date, not a generated calendar; repeated identical
  actual-date values collapse once, conflicting values raise a reported error.
- has_observed_positive_raw_close: whether the raw close is present and positive.
- mapping_verified=False: successful downloading does not prove historical identity.
- reference_currency/ISIN/company: separately requested reference metadata. Missing
  currency is left blank, not assumed USD; reference information is not a historical
  security-master proof. An ISIN mismatch is explicitly flagged in the report.

Do not calculate comparable returns from unadjusted close across corporate actions.
Do not multiply LSEG adjusted close by raw volume. Future dollar-volume checks should
use raw close * raw volume, after verifying currency and venue-volume conventions.
No assumption of USD or consolidated whole-market volume is silently applied.

DOWNLOADED_CANDIDATE means all four core data series have at least one observation
and no request/parse error; it does NOT mean complete coverage or verified identity.
NO_PRICE_DATA may reflect permissions, RIC coverage, venue choice or missing content.
PARTIAL_DOWNLOAD preserves available fields and reports the missing/request errors.
Rows outside membership bounds are intentional. Coverage in this report is descriptive
and does not count exchange holidays, missing target dates or disjoint membership runs.
Delisting payoffs, currency/volume units and Yahoo adjustment compatibility still require
verification. No terminal return or acquisition cash payment is fabricated.

## Repeat run
Keep the output folder beside the script. Successful nonempty raw request responses
are reused; empty/error requests are retried. Report and per-ticker datasets are rebuilt
from those responses. A changed request manifest requires a different output folder.

## Sources
https://developers.lseg.com/en/article-catalog/article/workspace-corporate-actions-content-set-guide
https://community.developers.lseg.com/discussion/25867/total-return-time-series-request
https://community.developers.lseg.com/discussion/114217/total-return-timeseries-when-a-stock-doesn-039-t-trade-on-a-given-day
'''


def main():
    requests = json.loads(EMBEDDED_REQUESTS)
    if len(requests) != 209 or len({item['ticker'] for item in requests}) != 209:
        raise ValueError('Expected exactly 209 distinct frozen candidates')
    contract = {'requests': requests, 'start': START_DATE, 'end': END_DATE,
                'chunk_years': CHUNK_YEARS, 'raw_fields': RAW_FIELDS,
                'adjustments': ADJUSTMENTS, 'total_return_fields': ['TR.TotalReturn1D.date', 'TR.TotalReturn1D'],
                'reference_fields': ['TR.ISIN', 'TR.CommonName', 'TR.PriceClose.Currency']}
    fingerprint = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata_path = OUTPUT_DIR / 'run_metadata.json'
    if metadata_path.exists():
        previous = json.loads(metadata_path.read_text(encoding='utf-8'))
        if previous.get('request_fingerprint') != fingerprint:
            raise ValueError('Existing output has a different request manifest; use a different OUTPUT_DIR')
    elif any(OUTPUT_DIR.iterdir()):
        raise ValueError('Nonempty output folder has no request manifest; use a different OUTPUT_DIR')
    metadata_path.write_text(json.dumps({
        'request_fingerprint': fingerprint, 'last_run_started_utc': datetime.now(timezone.utc).isoformat(),
        'lseg_version': getattr(ld, '__version__', 'unknown'),
        'mapping_source': 'lseg_mapping_20261030_062517.csv',
        'description': DESCRIPTION, **contract,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTPUT_DIR / 'Datasets').mkdir(exist_ok=True)
    (OUTPUT_DIR / 'README.md').write_text(DESCRIPTION, encoding='utf-8')
    report_path = OUTPUT_DIR / 'download_report.csv'
    report = pd.read_csv(report_path, keep_default_na=False).to_dict('records') if report_path.exists() else []
    by_ticker = {row['ticker']: row for row in report}
    print(f'Candidates: {len(requests)} | {START_DATE} through {END_DATE}')
    print(f'Output folder: {OUTPUT_DIR.resolve()}', flush=True)
    ld.open_session()
    try:
        for number, item in enumerate(requests, 1):
            print(f"[{number}/209] {item['ticker']} -> {item['ric']}", flush=True)
            try:
                row = download_security(item)
            except Exception as error:
                row = {'ticker': item['ticker'], 'company': item['company'], 'ric': item['ric'],
                       'isin': item['isin'], 'status': 'DOWNLOAD_ERROR', 'mapping_verified': False,
                       'events': f'{type(error).__name__}: {error}'}
            by_ticker[item['ticker']] = row
            temporary = report_path.with_suffix('.tmp')
            pd.DataFrame([by_ticker[x['ticker']] for x in requests if x['ticker'] in by_ticker]).to_csv(
                temporary, index=False, encoding='utf-8-sig')
            temporary.replace(report_path)
            print(f"  {row['status']}", flush=True)
    finally:
        ld.close_session()
    print(f'Finished. Report: {report_path.resolve()}')


if __name__ == '__main__':
    main()
