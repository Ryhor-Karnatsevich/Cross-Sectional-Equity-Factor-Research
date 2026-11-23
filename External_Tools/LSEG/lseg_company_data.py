"""Portable company-data downloader for the Fama-French research branch.

Copy THIS file to the Workspace computer. It needs only pandas and lseg-data.
Run with Python 3.12, with LSEG Workspace open and signed in:
    py -3.12 lseg_company_data.py

Default: all 900 historical project tickers, FY2006-FY2025. No stock prices.
An embedded universe makes the file portable; unknown RICs are searched first.
Custom mapping: py -3.12 lseg_company_data.py --input mapping.csv
Mapping columns: ticker,ric; optional company,isin. lseg_ric/lseg_isin also work.
The full command processes exactly that mapping, not an invented RIC universe.

Annual requests use explicit Period=FY2018, etc., as in the successful CELG
test. Fields are requested together, in batches of up to 20 companies.
Failed combined requests are retried by metric so one bad field cannot hide others.
Monthly company market cap is requested separately. No SEC/project imports.

Original reporting is REQUESTED, not a certification of point-in-time data.
All returned raw tables and request parameters are checkpointed in SQLite.
Provider equity/expense definitions require review before FF construction.
Missing values are never converted to zero. Identity candidates are not
automatically approved and duplicate share classes are not consolidated here.

Primary references:
https://community.developers.lseg.com/discussion/83314
https://community.developers.lseg.com/discussion/55788
https://community.developers.lseg.com/discussion/27031
"""

import argparse
import base64
import hashlib
import inspect
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading
import time
import traceback
import uuid
import zlib

import pandas as pd


VERSION = "2026-11-16-direct-get-data-full-v2"
BATCH_SIZE = 20
# Embedded project universe is populated from the local 900-ticker export.
EMBEDDED_UNIVERSE = json.loads(zlib.decompress(base64.b85decode(
    'c-ozPYjfI2x9(q|_J`T;dup6P;{H(x0W!J}Nr0VQXR3&;#8e1)V>^l8nje3jwYpnsLCaQ7&6E(tYDs-ry)Mss*8lv^e>wm4=YQdUXXXc9l(jO?'
    'okwvH&wMZav*kzb2l4NAyFI*WTUTwHzu5gNe7A=G^?(0F6V8}gp^p#o-`CcNzU-g3pSLalaEC9ev~63RZr^HKgUhz8!Bx9|W%XrSfqbCv`Du5z'
    'J+z$NX}>$<Pp#SM`0_|C7LR20uG*a|yCWW{d(|FY*=^a(QZ_SLJCW<PoK+ULmQIqT^ip~Qxcf*n(4lv-yQ+bJ-)R|qi0S0<ai6Q3<9#}VVW(rY'
    '+r9VtW;|ZYC;9w&z00f5->JV$KBJo-?vAJJpOx#Xw-b*&lGpiktFiwf`g_qH$_L-&_pR~n`1JbpoPU2R2c<K#x+A=Vec38KigjgMvem`(Be#ps'
    '56i{ho<)5g-#u@C<gN5EzuRs1&#&bO$uaL(9W*~28JnjumxDD9C)|2C!Tbqqn|o__{GQ+csdag~)9-chv|_j|w9vciSfUT?E6XmQHX6$=-<>`m'
    'K3DsWx@$z;Z0Pe$UN#=bS=I`iahy0=oM0(5SOl&^e?=d735O@TbGLnJ1%WHOqu1`-TIh5`cZ_Hv<IO}%Gqna1ciwWHrJp%LYnH^TWh=-g<*V2<'
    'Ms3UVFp+HG?k+z(znt>c<NmIgb{5b2zUeyg4(Z=xj1A7deA(@H+h@!l_xSzs<vBmK(){#ecb99^s6Dhs?P6f6YrBmz43ubnGWOJ}jK^M6=`!)<'
    'MUex!)S7r}-}NfX_^pdWdGYD)AwOMBwufE5f4T~H_xtUE-l|C(N|r!|gihwWt%;L4tz{D9IZ{8GHGLL2jmC-ROj=Vvf@JbBvhz5Ypp`Ru3*kU>'
    'S_-!|ua}W(Xd$2I<@tD@KYe>kJX9Yc<KEA(g8SmE^-qhAX@2)|+F=d5$J3)6R*36stKDyl$H8Q47sHB1yM@g0)ToAD;zcbtPL>TG#aotF`K}YS'
    'yufoaoVJ$n#!Jvl!){fp6DN)DEmyknPc0$(<eyH}TAT)s+wh5IYW3~+`RVKSV7{bH0?d*!%b%U~h96~K5@EK*ky`wX_hVmeIke%0w5|Km+Dpah'
    'AFU88Y3A`4H?Dg&8gJFyC)r$@t`aB88b8Oida2X%!^^34{h>A6?)TfTSc!NH_gK#LzAnrwZ7dwMf^p{f6$Pc?a4cA;Ez-YTo942+&wu2!`mfym'
    '?#q{_R{EUh`_}xpzuz6cRu(|7JHY;B6*m|tX^RO$9VB&@K<zid*bAK`@GA3=UT$C((?Ky)0)G~j?{-^JQU-GE8?IM!AaK%!({lX8G*d+HS{=3j'
    '(UVJw9H`kH1Zn1EUeg5>1YSACzwVBQ%KpN)FkhD?e77v2o!;sRO))=hNeqdTvj1(X+qG);l^zR6sjCGy5x061q1BmfajW?+daUKc_Vj&wm%lti'
    'ncQoemeuR@(D<mUq#L@(7TTQ6`=in%A@S8}S_Zy1!Scb%gxu!o*ZOPXHR!L<O_W*-b*|D`BO2ZIz;w~1qQm0OzMI6qxdDcyaL&91UG$f(evXPA'
    'rh1iHxznj1_;}%olp0BDoMBykZH#zqRQDBAJe+w^(}&jghGpWXp0-^!Y$7`osF~bVl4a|!(D|!T6JcSCK#BUUM8wmXM#+Xpr>(x|FaL=rCO(7_'
    '5jvk@+8{&u5>iR-VV51e_cT$dgoth74KYk2gT$4*a<XRiX|n#XfO*DN!QnpN{=iK9r<LVT$J0?71fA|EwA#InaaW|tq8>)=pw4Oc^t^3F`SZ`?'
    '>DyV)&^1H4#_%>%rE7Z$CUrRWJ!}b6KO>Ddrd4GgA*mI~{*97PY?sg{*(Ecf)$AW1@JL(ez1w{&!TY_ODhjLJ9`tXlwtO&Bhx<kQLd}u8a+LDc'
    'fe#ieEUpePqcjt$-?u-a$A$(`&Bmpr20=|G58Kc7aF@5{IgF-<w^TQqTC-&Xv6=u?Vf)66iKSwchJH40Ijy+5Ee%-8nXG`NQ|J#$9KUz3rOSWs'
    '{yi7w|6zN-J$*a2mihDPxX-b8AmA^5EQNi?hB&s`gSKJJM?9O=ohF5G*IJ&A_b+$PPozye<lkAuH`axhb0r~`a}V3DlnrMyuUy&Hi>2b^JRbM^'
    'V{5iQe#Tr2w}<W5oTSBth|qNTvxeBufDcTuu`nA&n;u?m`%IhInO)r(^xH6mdzNu|(3DYaD>3@`7#x4>4wb>A>4^nx?3qj{kdM#1AFX9j>LRw>'
    'cP}qW)J79{H;^^hAzQF>f|e%~3-9B~&n}!wGzmLbcH7vV((6xHyJgRwzXUy!Nw-R7Y(dYIsk4J7t{bhRPQO#g05ZTw$`K^=B_(4Lmeli2$dcvm'
    '$g0Ze?s(YU;cR~V`8|IwPn`U8e0qe!Q93TV-3|$v_RuyP0o}szPt}Y}=K;E~UcL+Oj3qD2W~%G&pSSy*mf9p=pI(bgg^DpMG@Vk8XUewD{Mvn0'
    'I?1F+%+$os!Z>Ytk(WSQt;m%TnfzAIFeKTUy;JxgKOrv%=MFP$_e8UNyx;xjKikv2Hb%YnU=1B@SUktDFcLZ>r<HJBlLC(8-*c8{&X4W>co=VA'
    'X{d^Gcrd=d9CpvU{7H8!^*Y@lR+DAd$_sUqnSAx}>A1bWJASY3bzPb?ZPQ-2Uh>l||8{tyJ3mM-Rg$ZC*<QEPrU^MPk3grGkn3AH0zdN8D@OWo'
    '*gYK&O$GIauH3*q7zp>^p1p&cEnI`FgKJ;?!~M(C^9lV`I<c%#Z#e3-hePwE#N?7X`DStE$K7nnd$b`fft^X)!|R#0&}S!@Nw(Y+n;*_F>7anK'
    'R#+7#<l5`iG;rZ;xLHELq_qZc<?35nUpPWOTgv8n$PceA?*RM$RWm9Eojz82ziSvnIwK21w5Zmd3#rJ~-iOw|Cf>iRCY$E!>=!26r?^xEp-p<t'
    '^x?7G(#Nq!4yz`wJ$9&F96v<-87*4zv?Y76vRUHI`&g?`W4rx#8&xJJomFKy+hA7PbkU8v<_1H5<{N4D{^Kz%8~R{P@mg)h9c%>ctI6VO{PK(m'
    '`epxmWzm3QF^tJ=zI}ec$?NfOFJ5$j`Hw(Gdt}zS2Wp7N%9}jSx7aLN)7=4DAN=I?3so3S?Y_KzBj*S|!XK^i@%~jTpEKRUV(q9?wM9e|Qc{eu'
    '2e-zn+r~aM6@3^dt0>+0?xNl=AUyd}HjUZL#SykW$uYN;pa*r4-XC;^ka8n)9Efxa`2-V^A2>o%xjZMv`|aH~^ur{-`vyT$YK|joFoK(=-8Z|R'
    '$zYI8s#yd-BgDuA@8w4+&i-h&9z1qM(Z>f0fpo>-(snyNo}OP0d24)vTj>cuq%Vi(Bc!v`3)9CPoU59!A9MztwmB9+8%ehqLQe|5DI9N$z$YJ3'
    'xC}gc{$?XNy&9{rj5kqh8YeL18@hSM(hD$tIeg8FcX4!i+cEC+<M~u=mAkJG&kx6!r@UMNXJTL3s!Dn2DqUkdSBlMeOG7??fz*AfT{?w2FlJ{e'
    'j+i?>>#F13*H&<ReiB249jP@A;PyM7s;U6(Y&J&4HY?V)(zwRHuR7I_rB|bY#eqLAuDVJP0?;E&XImNj`;~I8M>faTq!#1&_e3m<>oOuEx7BjD'
    '?)ADudZC_qX>^O##)~at3AsIdgE{}Rbqi6`3UgQ@2a<*K^YP2Yzm&_c--Q*7Wmx0LC=}}PB2v@pc>G2lSLIfz8g3&FZW+we@gljL6<Q=m&IN-e'
    'HV!80(wE)-K0iHSQl6fkQ+5zs#0iB9+|Y_tZCD~D$Gfxe3q5w%sD_Md_r43epNuncO~|`&=t5=o*@uhsR(kyM{BwKCHTAJKvdLN6HqYIW3bu~J'
    '^sU%OSJUCfq1r#7Yh^Hy!&~zIrLg42<7Of=@_AxWI9fy$$1fDk|N4xn6G3Pq5^!jx+XGxk)4Z6smTe738MKMoh@ukdk$S?nr>8y(4YuMqDMX|L'
    '!*w##-HmA+tVq*1w_Jr%W||*~%liaA*rf04CIdYX;`wCOi&wQQvJSB!7+$qcUu2YRoGc1S?j?(K?k8Sr?qqXk<5a^1qJvBeCkgnuf<pVp-h8Te'
    'k@tt4HdLL_s7}|n<tQYvzQsUQq0cjcW=R=#`BW)S@Dyt1-&65a`SwIXneFMIWLm`r8FWS@rt5G8y<+oB)rKFZv|*;M57WV)BE;Bm|I1b@@-Oly'
    'X^j)sYL@x-Gbv+I`!7V`pxy0tM>hO3=3RZH0=VN9`LJ*-Q5uJb9D5}8rI)9>2lkbTAFjj?hF<9OY<pyu?b1CUcf(Dg`X{pu+!?GuyPC8jIaj(Y'
    'I|@fJzR|?o6IN{A5J)k;2}t*)4=74gu>iKe;O*1^K?7?rfUCLFulg9&yl023XiN?iPMW&*6m|v<CxM!1q$;`8PcA{27W`H)a@5mWHuTmdTyBH9'
    'aIu6qxQ^W0T$m=a#KBU4BPV@ZLFlVB?mE%|<T?ou0R#<z2Mxa4hR+}Jr6Hy%^{Tstq5~P|A7IxUSmcz}2i^(Jej7r$r)xX*NQ>`FH4G1v6psZ}'
    '1u@1T#tv2$uF8>Rc&zkRU7mWkh#!&Dhy*JXpK2J(7PlRl8p*hUjBQbuB5+GT2%Mw{q!5w`v6Qy;9wN(?Qq+BT`TV&RJl{9yS;np42(yO%**zW~'
    'u~s$z$m+1)ecuV34F16P+U;?-y%<?Wz#HRsq>ysQb8dSMSukN)Kz^zm`UvS<2o^pTOCHVitdTiZ#3rCp=UiC%@+ChX^U^te`j$UGU25MQV{qCX'
    'D~~Rn{T>3r9jEHj6vAw|J#D`qVG@yL^zHSY!yo^&);n0n-;2LBTf;&Xab5K+$2$rU@3)Y?nAVR7Kjoy>Yrnsoj&Q*4zOaAx?DxC|j3HgV19h{d'
    'TE(t&<;H>2@>WT_bX?v%2vrf0CZvaPd9RjA-&t$Yj(2%?#3IOoD)xz9vs1+9EB)w7h0(=cxcecOFHPDegWzVjw0rR<?Or~6uiV|~?qvrzI-z}p'
    '4OGgxfep(PTWkBh8Ro9U1FRySg2R|0h_3pKz^Rp10zskX{lp=$faBj|cG|k|6W;H(WNb{fuV0QQo+HI+@rb?tU;tQ>^gvei3X)mmAr?1?)FgB!'
    '9$`QyUP>s7^frYNot{H1%zK$T*~msFn~K1*Ms>mSVyY6zB!}T!xooHhQ1tEA^=RwB5&jM#WDan`0xrWLAgOE6gf{$K4G@vVH?Yhek+UZa#65!<'
    '?|LKg)L-*MuI&?W>ycL39hujtr3^c)8Wv^vU>Gn@wj7~YQp5|@9>WJjO?%X@YAQ+<X)7Dsg@=z@O9<34Wm6ba<e<BLs4=o{rPooIv?^R@OI!sv'
    'CfyP4R2SOjaDH0^tqp(-cj|H*q^ZuNsD@BGz5d+Y=VuPS*1wjg{3^ug<fng&QL*jLfF9PabE2u0F`bqA%O@{NHDjbuXZ}ijUG&&y5kBQEoRSNz'
    'C!|RJ<%NSS#dvhBK^vx)v=?L?%+kUR66EC0W!%-BuLzb3N8HAr%`>^+D{)ha&N1!d^946SZoR2MW5IaeLN0&H%Q^1-dL(eBre9Y~rhd<Y4Cr>u'
    '%9#GhiCVlLTJsOBBpwTY-zH81JpIILyr0c8r2@?%{250QhLC-(qnU=lmBfGPqcSqagNprN_w}$9OSi!j_{tMVXHG){#`P7>0%!Q2eCFD0YT8IP'
    '`zWU4jQ5d%H8l2|Twxd4{U?W=#uoS=t?Y!=r5sUGckaP21cBW%<DLf!##QWfaWJEZ@zM#xIPlkABUghPs5cF~wMXI8D>v|`(=*+BB!S|kr&VdW'
    '!Hv2;PU4$4K`7N5hio^5j@rkLBH~qwV<6bNZ8NlicC3D}1B9+}u3~zTqR@1Na3QZN`YeETco5*vpD)%AJx@EbRS3fpH~>pqxt4k!wUdQjDS4VK'
    '7X=@4=l(J#btm+0IP5k{ptYZwpTZ4kXhf}(RTyI3HZ+2idkZI~==2*`s^(paFGiOb&W;fY;zmpDvSb+}IHhjf?1>{a@uC|ItW+N*>T9_IZmed#'
    '%o3o0;BPPRn6-c`aVV}KCNVr5&#id32Vz&K*HE?@rK!%!(B}ua%m-}>!*oV^Sg50vv=UV1#&ac0<2eDw#Vr4z8-X3OVuij{R>1D?dHbYHn={XC'
    'kK>4@-G{L@I7$nje78TLOOb&9uVkqQ)9ymhQ>$MK50_g^9IJPUmttF3I?*M}rC+No#)YX7#rQJE`tX-&lR-<~$Pf}qLB{zCUzoaMnnB8KkbdB$'
    'jsz{Y{))U!le=fisE=j*T6<RxyA^JMQF+mtFIXczMhK`M(D?I%G{V_v?hn(C6MJOFK$P9Sbc)+2I6w0>c6kOF;!^HX8UFx%jlCfF@ARz{kbZgH'
    'j20<<d{8Ju%$b+(pLg5Va`%{1hT54HZjFZauw5dIg@?=5JX}iOTPj`7-NK$N!y%e)qGDcFG6!&VF`i_YR)p(NyXRR)WJO27IHFt@Oka#-maNqL'
    '5IVFulHo2l33tdw0J*zjzj=J&pu|6|^1M*i?RKx<sc8Nca0Ip;)gOuSf+h3Tay1TMawF|Y(*gwQ%LH9>lc3boFs)k&^oOJpXse<JF1^%f+w{VT'
    'gm0!mSUs^xdTBO{jKNSh*(lZdbo_ar!uWu)TaP8~8}W5+s@~uAajLA?#u{uoTb9e-G3E)_w)9aOu1;9VNqLKy2=^$y=nm3eyNuY78eu8%L$k2J'
    'xVg$FkCUd`Q|6?F5{vW3m&vIRyZ|-`nDgDk;kZA3)!|=eK;B5X&d~(B9W!=h2Rtn9mN0f2z>{pK;gA9)%HU~h3RMLUPFw87PTOohm0M_6i)2Zl'
    'h?^<cAolUd|K#Xdytifes&Tiil@5yd9H7c){z8EzH0@*=i^%K-rro?PTnTW|{nAW-_-Dxg?wSn&y`@w%l`>9{P5&L1&97E^mcoi40?@GL6jm{v'
    'l~7r;?Y?$pJOT<1aM%KPs2VN(3U+_kcZ<lE)s|yeif%QaYu23BGYPAQbLIyPqt=#f+1()l{B7e~muXh+n!P7$as-R~TI`QGxfdi-yyfZvU$_&7'
    'eY?gj)6wV0I&up4JrYUCcKpyllCIUFTc;`v(F|hfuGJEsd+Q`_3N~?XNWS3+n4~58^6ufNX~d-)9AL9$f!Gx85A_NbYYB36J}DJx3m*f5{p>P+'
    '-tG<tgto;xgRMcMWw1`l?nw+I#Aoy&>Gpp%Q|>1!oqgg3nMlwAh{wB3^<=n%>3X%eC&%MyvVD5E)O9<?{o>rc`mQ6jd*($dkZ2Rt124-XT=;Nx'
    'MLE3rr^ZP8$t0Hc-~__+{`mFs9R|jz&qTpB%<g1PnwDPniAt`Wa9C*a-*4@VbceRGx>f$x#Dg)?5DGT&+=aTzT~H_>US*RwPAYR<=%FUBGG;>{'
    'CPl!mQd;d3GDHZujgMj%u)Bk{onWqa-+Lmm11HmX!XBC_ub>H{9l$#s8Ih)aagVZXI3%%K)xn*5WUz>~Q*J!PmPPu_WcPFj(R9*Wo@oE_M}<og'
    'cS9~^dt?qRNQ+HQH#Jvcj_;{xVZ|EfECkagG?_`+^KnI($BB<zT<AN#+t7V5nM+lC9w&?uY$X@o&9|<W^K}9-J1?@$nqBM53A}-<r`|l|uZ_~v'
    'aiJ>(ycz@Yp>DS9D+lo8Nk@j1u|A>Omu)O~@!%6Pa>9a8YvMyOzOS0%!(%$_D8+~TX$6w+y#2Xoo<ai-%Pab#^2W67l9~+5t#_b@#yT2N$RtpG'
    '?a$crLCGe{fHCI3n$}^U{JL_sWr=s@6t3bUDi<@&1dhP?j95M%2>Wu{-Xp${=fd$uD+9lmzlyi)cZVGhYKx^K=SviESH(RiQNs5~ToJ)zB?OTF'
    '&o4a4>a0)-x`UC`w~Lfzfu=Mh5lmu!=V>ZnEka!E5Tu3MJw{IS!;#Ini=QT^9eGN=mUryg1IsPb7C8AsCY1@VM@QXJE<d45EIntTtj<gHW4A67'
    'U=pv@c#&P#Od*-X8@^(L2<U*f(w{}T7`>$a)ji5ziWlrtW`-H6TfNKjlcp&kH)iR7`s7sL4Z?0WUCW_%9Hq89d4YwP<V>nkE{#5=Ljz{tGvx2-'
    'y6!~z6DHUQVcaK_g2kEpO{HL__C!kDQclz+*RA=YHDyb(DLes6&E;QtX^+|t@b<mB93vSBn5@+1`cg)PnkkVJWxPzBHKf9Y3NSE|3{2LM+RfL6'
    'hR1hol-)hqD25PB9HAvu1IuM%v|u^li*DpV;G{H8>qWlE)gGy9L-oKnWj679lk8T#<?A8;`dX(`l@^Ided!S(N~BdGbM+31o0RwlMh8+V&VMO)'
    'hGDNqww?()C>}}*IB%>xd34rndcwGslhK2PkUj$~SW&zBbv_hNg_u0Tbc`FiPP|Fsp@lK+PdFRi!}iq_gYU6!iX-geVYMGgAujAs0A)ac@XTR-'
    'g>3=ScmG168_oV1_WG1%)UClk4pj<@H<ii|<z7ymn}$y-^)E!xNN^}eQH6M@!<o$n@3QBsTdMxid~FTxy_hU0)X1L#vO-(GhcMQ6sIQCT{q|d-'
    'zQRdQ-C#^55&R{>H1O1*!(ryZ6}Xz{j{1h36093!Z_9*jgQDRviW^6~QD2<tf_(^mpeFTCgpvEQ6)BByIcyE~H(%OP=A>RPl&jxET#-{i<{tPY'
    'ShF_2Kl|{c+s+FUb!S*Ru}0R@WMA+i7LfEI=)-t%dWU=3Z26;#Q4|Ts91pnetVc*K(?bA*DsWBQKqYf~2LMi<)UI)9<6DJ(s@wRUGEi|s+hq)h'
    'L*uEzueOBG#^(6}wA&NEmpm(%ZKu-@ifq<%L?D@4QY0=F<qe%F>2UEXG{L)?z*Akp>*pgwR7gO0-#>3p|4Yv!PKw7FwFg6}puL)~d=Z}TKKhy%'
    'iTs;$0zGrE&ihC+W*sJr544+m|NBCCGk9}=l{q{Mn{mDS@g1N<{a5*H-2ru#F=DRg<a!@7^=R3-GFYRv6G}~9gEPF#1S^AbFtzYPw=P<zQqoB_'
    'ib*1s1wGZeqwq{;mnJtXgpwPMnD9mbd+I=05X!@+luk-R8qLg@35g(+gOjQ!N>lIVER1u>(b6@~;FN^h+6k7LHQ*g!@6i}-_gid4+L>6LvoWpC'
    '_4TJoe^?i!mg<U^F>s1L*q=+I>iwS#CQ*Kw7D?i8WOtEGWP;8TF;%+|hnW&-ylJwz)rc9xQ&t~`?4_#L&`$R<1!tzSbInWl`<FRe-g?d*fRBQK'
    '#XCsvvl#k25jQjaTCUix)twY6J``uQ^-0lIDL(MJDslGXQVNR1m9`;Jr2@a+JtBAT69v03`O_T&wC8vPnc-y6q&=n8dN*Fs*!7D)R#z>F_dqG&'
    'XKWQ_M<=eC6jwv-K$Pz+#z$$(8#q#t_}n;elG>83{(8)TOEvAbZ(Xit*so^<cT#4AAh0b+EH0AXEu)~4zz!sAf_o{>*thupji-*vu9LR=XUdv2'
    '?S?{*n4D-+M}>gt%!@8`1aq8oDr4(m4xM%hfGYgW=lfQb)KEY))zxz;%FdE${lnq-gEfPvOTK_o&$l%~wrLUGp2AN}^XNdieoF#?pRfxtNbS#a'
    'Dp`h~>R(i2H!20!^OkT6UWIOmXmZ1eG-X!{j?yBYZolvLpltx+gtMF&f322y2U{NTE{@u@G#v7wl)HQCApYlNq_lWU7ivH^3uVESdo@)l(NhnW'
    'WW&{pi`3lA@4a8G=_#iqUyVS|K<-fJD3{I2bvE@Anry#;*qVAu&P_4BU!E$4lQ2drLR}i3rl~tsl!?>c*{<2H?YnuTJvc}_6aUj&5>Ha|2rX^u'
    '^MxO>`QHonsZa69ryr#P&_Q5xSO#Z0I!T<Gs-hvaG^Z3?@>9pDX19qXZQ~30emVFFTea|6hi~#e3(tE;y@Z;C(BAf>-bG4-_YbuA1x8(k0h-EA'
    'G`r^BN!QGp_IB62)lN26BQ!<yGDFHFG8F)gYc{)-+6z+=LO3f{)+()f^=d<?OdUE6;I-uuJ_1n}9ErR@bD?*-V4oQk#=K0t>R$3*O+l+9-v(z@'
    'bG)x7i&vk(PxuO-U^*V_CiLYZjt+&h+eMVxDjmmVuUL{kQnZ+;r&yhZyDm7p3SZYWP!lDHH>sDbFL)+PYFQD8m3G-Q$m(HUmSUdJFkd2Pa2m?d'
    'nTBVno&siINOr_uy83D$R$ic9gBWri(mtDk`|xcNj3UE&8ih`^sX`GcS^|}741^~A+`^U(M+Ep4y#{T^X`pttrze7EUTP(lj@l}KW8!K#g=~v('
    '!ORT(ilE>x=0*6WBZY|=aEf#Z8N<ka;*VcNw!D6!ZU>Hxxz)I*^BXrs0{2sK)8BZ2H`a0D^5#uh8y;&OqLCzjeEGcRB(bv}2+A%+P2VCMh(bz_'
    '&K$Bm<sO+T44xWs8I00scPqfU`jm|+TZuSAUFZsBD95t}z~ho@kn>iGMceHSNfH|AhPs*wKTV5O%X<~vm`?KN1u(vC%o?96jxcso?;dGQ=~mWA'
    'Hz%0nNFo!bS(KF;9RQNgmkMaxh<cc^eTJhe-9;?7;4uYv*Gchs32r>5^r-n4q#Y7pT+v;<QM-@$gVA0cNV{F!eyu(CkFx|W!RBjFB4!Gv=F9>O'
    'wt_jmyJMzJ&`b!z17NCaq20xx&7@VM0^o4pJ0S(Kn{8jS$wb<zv*ToYfB)JLXQ(Jw)NOyu(KqwvuDV>Bunbz#!FLxpWy=`po2h)48Nhp!-Phgo'
    'c7N_{B|CIzy!4ZJgHII8<{5@o{`2}>gQFrB3&cU#cn4;#t|BpH=B<lYT9d!#$M&Kt&3=^`LoRUyDdtd|VO{`#v@aF@zBTBAiqsmJbD4$;-!dyY'
    '_OyN2mQ=KL@uCXf0BU=v$%HB&Af90+1h;vGkD1c+)T{`BvT5iaRmBV_X&f7>KRru+RZ5QG!cDRHN0Mb9@budTw+xG^lM@AOc!cDvP{efVNS9}V'
    'shK`7cU%^TiyYMWU$NEZn2I5#`~gB%h!rqC46Lx+B)XcTLgs4NvT3!nkeCm{?~y0thgwO{RqD(vN?g7B-J)W^1$en*R0C(xrnnxtZ_tI`XH%9o'
    'u$+Cda*#8(?&tjZg8R^%{7)AKZ(RAt7%t0qhTGYb#akLlp=DG~IlLk?N7{m`8NZ@~O=6t0FJ@doX0~PB;{n+I?W3->_u-(1Z8+?hVW)N>Ja{rC'
    '<c;U>zzhH^B!@j{a%gCGhO~)W=CHs(<vh$16~UP~2@nQk0#pG}rl9YPUnXVRgc)WHMSfDpou@6G8G{}JnV|4EciZoEuH4fxvXfhnATvJ0=91NT'
    'EUGsA70>^wwF&IvbvANNZa!>K7a(ykpS`51K$@#)B2EH-ykf9clevMk0KO{0+NR|{C+?ebjtnhFxLD;DNH2*Dr&FsuwB-#_^<*h{a2mhRSP^{B'
    'SKz1-o=UP+)43yAGLT+6`Kw7wq_5!!z<Q705J~8tg)dEQJK#I*khy1DhA57u#ZKo6T80zNCw<{NE8}w2XK|TXj6OKQoS*0Ap6N=-U!WK+ieBz^'
    '`a};nu*?Fft(2p=yJVydQ}en@;@{OU(uJc>{Y?4A)i3f-R5F0LyNwb(02X)J8sS05(lXtp9i>vC*+iVcDcHCq#+)NaI7&A0dH$qf#k)ut8qM+g'
    '12aZ)pmv10qF-0YX1p7yoVE|O7GzP-WX`b|>>e@4<>u2?x;xzMw>#2M^>0<X4Eo0YRVmuyVUe1^)uY-5J}gUS3Gf}6j&DwMd}8Tk?9)a{Ct;G@'
    'b7~QqoyhPeGST-uJags2($)+<9HE;`U~pYB>sg{T!(KI4&W8DJPw^yhZSL<mwckikS6`N6&gv(Q$Tgt*EKb`maF6D@!+)v>TmW#}gKi~f^2}W*'
    '-Mw?Q{c={*?G>S$Ch40c04f!OpfB9;d<||G-AP)_ob~ZLZCAtM>r$e!Wt($e3pnRo(edKMyWM!4()-(#thiVS7jR3xaw6sheRh>3$<RhD*J5(~'
    'ygNLgcg;LE^}vXEobj7v5}HAHqMy{x9GN+LqLwFHj?hizgivx6C?`PL&}W@G<c3<X(qfzEd(I9gLf7RMIIJ^CT0!WxC10IrfJNQXEhxk0;0Suz'
    'Yr%sqGKPBCqWZme2*c+pv^CFv?(^qoJjvZRVrkW2N1CoIa3H3hTYi-7G-TMCC(<E1{{y_RLF_K-uhSDp=PIiYPWI3XKw=tCQbW*oR0kWKCnR=*'
    '`Hk4|MLav`T%H=U#8zn!R$hm&Mm^0XXB#}7bH+L22$QcXM9Kc?VRtH`S!(5@+`({UnX!<z#^FCt{Q@@|B}nH2Y{!o-As8lf^E_Sh!z?kgd9%UN'
    '+MTxAZcEj@Y76WzmRB~UBxB5xj?9CA{eyur(8(L`eJXH{C__5;nn6nEP%D*;ACJ8%d4ME=H@*5QR98{mnugPJqb{o9^4FQp44yLIkvG8!CKc<H'
    '%x|C9;*=#`Pbf8h!EDNxZuwGz-+!a%WewWPTwlc>%U7w&<?$+|?4uOUW>7OkjSHsviqnW6?2fd616*rRmAzkg4_mMUHx2IilN;%S2K~y-&3R^S'
    'rJfS)u$Ix)=6hNrmx4h06b$<X2tiE!g4%9tf(@VoO+vJNQDgL%&-M_G@H6#P2Ni|{S^65dSFF0;i0LcsPMz0QZrXmJ3_dtpR<QV-GfhTV=%Y&_'
    '5&YGydQJECtg09Fs%@S$(KP03rqB(MHb&3n!&0OT6@+0T9eo_mx&x$+Sp_O@pq0<DZ4H%&K6cCAZpuc1zg-nqfgQi0bb+gVuIA_uI15>Cor8<z'
    '=>no@&T;markSyHmeQ&PFG2(B%U_bFhNFz@@_dkS1;GyhmfDidvk=AocAsl#T6I87X*Q!}^_<IDYYAB#N9RsqL4u^^;q;X`=YN#GOq`%Ti_wiF'
    '__$5VmS0FGkXk*#AZR5-(*y?z_O>%8uklB%kjxuBs50$+${h`3sP;~E$CJ@XlLSr`B0$U?A`gO<F=L$T*?R7q@17Mtmh7A<RV3z^#8D=%!pR%4'
    'b57xwih`eQinR?}%ui9D3=GTg&Mlfsp7p0<zUPG1J7)zP8sl--;!my}HwHIjnH_%SljS;ChN~S;u%M3*@khz&9Am3Oab)L=_h{Jf6R25Hyk4+4'
    '7jyc0JkLryu65lSBU*-{TT70*BV2r5?ykZXTYbK9px$rnH?%{p6(QI4@!=pUsT`<2)zg_*s1daAnjI7Fa+z@GYRp3r?}-=mkvK#DX=z^+U%Mzb'
    'u|y@8T<j73!HCKenu8M^76)RFxc2A;X-u!drTLlGojfV?21*$NMv}nHn=HvTRiko~yw1OT$=MB7!Za_da9{ZNMk)c}dNIE(rrV+=G}u3i;P=^}'
    'Dih_hPa`#H<GHNYAkP|%N3<lVMIXf6!ZP_9F+%EoRkW_`p&@1~vTeIoo&Tk+T1~l8WW=%;@p^lB0iR%gAWnJApjF!XmvS2XyKEktrj1}v&s-jc'
    'M%9+h-*WS}#0krG#PzXK0bM>V7FT8_DXJ8dzK*%M_*U{)FOERwJiWBS-Jw$O6gddwd4Zo(uUIqGyl;|D@p?%j8b|i%;1kT!oKXORUzI^k^Q~|9'
    '<_&73UvIdXO(gS+K@3mHlA^$pSPwm<yio1$;X95Fa%nB3<8whQnG~**FNccl{hBIVJt^<F35T=a=!3a_xW`bth(Me${r@OTxM6Qdy)~*Yg(O7%'
    'Vk{Mt#h5`Q?<Za@R6d!EJWW8-o<9o8;mW!bLvqof3r{XPoD`%^4U`xBd8%&w`oy5VdfF7pdu`Z-7qka2h{u%H(SqjKImi4zE#uFHD`N!CK)X_U'
    '*PPq4P+?Ks$5!!O)KofO_)^Qj3A8(j*J!4pE|i&u6H&*wVQhU7C<_s1O>Y*Ciw8x3CBQ=hys>C}wXd#@DD6qC)ITrihkM3Q*dn|sm_x#9{+QL)'
    'Q=N3z{30&7lUvN4+{Dgb#7X)t306njAw)e=b+sCh1m#$o0i_qoG~+9#S&^+OCXsN_R%LAubxryo3+nA^F?7Z3#m%aOj72;T(l-*6b^q2PC5s0~'
    'NG@J7+rtxR_XI<;0*zb{$`Y;2pj~F)cVrHc7Q_+qf3aS9YFQtCyyOO^IMe7W`lQ&~H1!j3A#AE##j%B&!c|;NhN@~6zmo^9teq4{CUx<HtQLS!'
    'YrAG+7WJ=0_XiVI^fbtK_s3d}U!4ZD`Uaf-h@;GT4f3yF$wf+r4q@5_hDnA-a#0hkhjbP4qYZk-rz@pZ;LXF2+&n%>JrqpOLH<B7NH}_Eq@OC`'
    '26clGktVn8T6kbz-ax8EIEkF3^*h2pkh>H-GJKiQIDG4JDJ$Shr7{6&rBb^h$USq?n3<#qBSH<~gA1t8l%`yia|`qGw?dWab!<y39Vy)33Y5Vt'
    ';gZ`VP$4AhvG}Gwj!|F2HBhXS0m;}(wba@zGVoQ3J+qVP#icJIALjhJU?H9FIJuxI?G=~wWF8z}!lW}eLfnmbq%MG2g}2+Pi^7gH=X4OTgNHsC'
    'EHmJNI#Br*Eu&p+>ab`)*9{r^UI;x1REAaH12BZIO6z)W4$__;gjl+5xpd*XdO9Ae3&|?VHJ`_8N}VlG<-;jRG55IqIfyEnCNu?V-e5{#3yewx'
    'aQ*cinO7sOSLL<g9dJrQ+4FHW8^J-$502;~38dgioE;S2DFy<Lf3ig^ovPI;p#Xh_;0)r8>V*yaihnC-I!ILJOn@}jB0=Sh$fqV3El6oy;z+o4'
    'Apufffr05Xpx~vNt`;SN+kLY`wO~RER)O>^?qBd9NURPmY(xlwk=tT-R{YBxSb!roYDOzq?C@HtJh=_5q!$h;q}hB!N%qLy2&6y0LC3B+QcWMQ'
    'P!?j@<v;R$tD`Wl#ZcRTIYu32^HX`R!lO?07Tc<lR-owK0uU^&Jz!Y@6N)D3d1+sb+O_gXYNBkve{OAZsuonU^<Jc%6`VA|4Ji#c;+4eK`-`)K'
    'D_$5qC})obgSwL8dX?kgR;themGOjCI7Wu}z5?@!KCCPH@W?zVZ{@%R6qt!r35HryIpI|?NpER<gxkB<|9+2-vf$2CX$2uw=RMt(bu~456Vsdx'
    '9d)5UDeAX6gr^Gy`!ZA6XL4azh<t711PqlKgA;0Pu1#CXJvh=kpe?UT)K$<AVs@3DZMF>|PNBkB;lz!9Cwn(^GIeD}A&ED+y`+XBghx1*iULmR'
    '<B1hBK6E8E0Vni^lcs8P=qkJb0N+VWEb2O?XCvtwDuz0oAmZ0J7dKQx84|!R{jJWO1kxoP@;b}^Q?qv8ZHJx{M`;etw?Dt-uW&HmfkfbG$E&W`'
    '(TAgMhsr+Hz_<$ri*TYwKEIdbD~%kwp+|}uj@V8u1!HYFkB`WPzk5JlaA~P3nL7Xj7vV65mrUrErBO9tC34dQ4|RCOz`Uc)x)r=0xC&hLJ1Ifs'
    'i$jqi+~{yn=YHy_yQmlUGKIcw^4gj6embwr;5EdGLRR5%lwP3l&iRt(S|1@7qpRzJrJyYQj@*vIa^s``;#6jp9-b-ruqw|oS4$yAwZw%64Xb!G'
    'Dyhl3-W+mfGLG<{+F}MF+#&&oG)UUlOSgM(h{C8Vs3$d0kB)Mju&XBYp`3Gv0oM0GSk(Q~J|`rj{9%u2Ab*qEQ1K7qXW75jkP10<I_70DPzCD%'
    '<mbDRO~AYiAyi%BczZlb@@~3=`aw8jxm;xpkx833Apw&NuSr$H5ld&l{kFYtsUS=Af}NL_vh=6I;WzAzN+5KlQis6W$z~U7_i-VdLaI*vN8`%Y'
    ';Uc>!cA*6(`3=D#bX!-qPfPt;XNw7guxNs80(|&h2DY(~>e2yJUu~ybN5UR*nqmkr47*Es9MyQ@mBPCK5uxp&3>O#v6Y(eN57dYcm_(>!?tudR'
    '6^eO=i6$6pI5~m}q=i7xaTf1Ct;^poq+FkdXi%6^Qr32LkD`=6q3o?r*hsq#BkqidN(2e6kOlHCDC-6|{1ZwAk+Ya%$=ne{M|k(`bi997ltJTJ'
    ')*19V8YQJQx~$J0Mhesvaz!ohTtbCreuhfAmt6-v3}a=YL6kVZS04|8NJ%89{f^{UhL_d5WMuE?EfmUf7^`|Ub;;&sDfy5CWjJCT4&@7@<nECN'
    'TAs>92s^6Z-(Wi(n)8uLbx8TyaN<<5!z@ve%_N6aN(ZJd>@F<*Wln+C{N?)vy@=Ve4Mo`j@iyo>q;#VkAB@w)%!e=Y5lthIs67Fi^f%$fZ>*mr'
    '3b+~`?`b2tq?sBRor@tC%Eb}jkgnbjRA{C2UG;mM5^hTCwAp}DQ#euN(2zhWmE;OtcKk(kbx5Qj=$amF9TbD}gRG;{gJWWHFd=EfVoGp05Tuh)'
    ';5A6s3R4w<r?U&P8gm7TFlGNeeK1P^YszUnEovr_iiB>2NbL6BeE@ZTCHIPLyz!h+Tm#`B8Rcy>4bX&{tHyBq3?0ve@;fh`TnYh|0R(LgRhE#8'
    'gHkS&_|mRAuS#ZGoY_n%T3AzB;__Qb?`6~{%z}^PkmOHMD%nyUN=!n~-0!z?yBDB`*~%3}ENVNk+77l8tB#ILdiX;HoB^&ATtA!GeY4~wBLS5r'
    'ywZ%S==UwEm6AQHWI4ZW#r_-ayy{-FA-@5RGR{N}k`tI9TKK6{iNOztqC>{yj{@)_THA1I8|f!e``0Br9nyTzMHqEp*Ogq6af9%N!=d!SY@b2_'
    '{k8kfs`gh7bx_L8{mb36Zs-gK_M!kFR6RSEmb@C?D%tY7=K`Oo{0i;wsm|q5lJ7)FbP#_PZGY^@vsL3&5`I2Q->8JP7%?IU$AWq+I->N0R&PTg'
    '4BCW;?hR{6$40U}ISV2}uIhOvdP3gC=oM==Vx9>crO8)Nrf{^c*aZ5W9?S+a?Qq4si(D1B0c_%D{*@}Ix~CVy@RKXP5=hlCexlOm#Uzg=&PVlr'
    'Db6o68Y0fOP1mK;FB&1a=iJ>Oaw1KnQIV$}o(AQN3xa=(PxrOGI#4dvh^=%S8IclsHxPhMwG11Lai=qy7WpmpD?Re0%8JMt6b(Tw*w6_QO_gF6'
    'f$%Qy&!grwY(f!pwc;qr#N!`3fUJK|Da^g<k#eqDHi1QlwxK);=U7ThDN<|4mt=*_w9{yz2E|`^O*g=3p-A;2Z$SlyGQj)+o?Q|7eifN&jdX9a'
    '5bIG8FW%1gml=3HJ^5b_e!z2&K8RkAr)RW7?oNI<#}P1V;bwY^)!r-Im1Xe>TQX8`tBSBZqKs(}D?-IbB|<0q9hX?7_{wqeMn_s&(INb0AT9_B'
    '_JVMCcRB)?aQ8yMzAw)|^-3^(;tYeosn@AvGO$(4a_f|gOwsY@pN1|rX|9pN)#602fKtg^vW#|8l$QNCje|vtqaM&t8fr*UN{bOkS--jvm?=@V'
    '!_kO6iRm?J{y`I|17ejlXWLnl@{{kFIr6!H5QL|%@e;@shJ~jLy&|)|G<{Kp(uh{>ThvO`i`Elqi$q8X^qt0+F(ngyP<3UNh|!Vsewtxt<WM}p'
    'phsKnx@0A_*RGWaSSRPM6thVfZGuA5QgY8Y;h<B!oYJGD(Izb}J_}UU(h=brr|zOoo!J@PER`g^Syrc4HFQ)@!4TbM#cf-+KzSo?KCF-TRX}dh'
    'E$<DtH&FOGd<K{$m9szOzm)b&rcTWW3DlGjv+`~QJ&{Wp%;!DVHG&G`$yAONoMo+|91>U&xePRgFaI>4$W6}Sm>v8$5)&@_MR6_>S4C<i)Zqa('
    '>)w0x-Y9w|AM5lLaL<FV<@FKi7Y3vV>&olokj7U&%7|{Cly~hsqtFZxh}9m64A^)fsYx`PjmYFQX*{taCyT*5OyvE)Q&~4=L>`WEDxfe21UXc7'
    'ZL#)kdudj3+C!~&nL<xv3{zqPkD<uA*?9>gTc#CVK1rg;^pU^i23|wKgUZ{|BS4@_#&$TXEC#_T<!YQId321V0{Bz8?&Ig3o|RkSi*46YlEgRa'
    '0bCd9V-eMkS%MK5rt>QNoxL3n7P+4;QR2SkAZh#@Qm&CVnv_0-U>()M32d!kmLZy`Z?E@EG0%3=-SN9SPR|tSftLO!l^~FuxT>vJTvX@@m#73w'
    '&;BY56Eq+dS88hRH7pmf9J?gh=%Xkcw9Jo>`~1J3TB`#i`O55pqQEYdH>{Xj8us7T*q4^$8MhAd07R17-1y_u4&cG(XD&oj#c2*Kl-eGdG3Tso'
    's+^Oh3g@D1GIH2kV@9~V9S$C7ajB)NqS;Hw#d*Wda-|xzoc-Z7tX{L^b%rA>1KL5Cdvce8i|AV`+kO9BO(PMVV2|vcWoD-l%yTl3vE*bG997e&'
    '{7%qMyMP!xZYkDQs80jvPL#6Tt7)~!Nm)*KQ=<=_5j~!h&(9(?;xhLQ7}m~+OkH!aWfG%u%uq9^Wc~R6C-$gX5?w80ajA-5$g;CC`KTpIdjr(y'
    'RcLeG8#(x5Wpg-dUVYHk5S>eJshU_K6+CWw=PcxFvXFs!JOuf33Or4T4H{V3D+rI*)-laJJ*iywilXRUPW?|_)2TjHU76tT{Uv4D7Nk?Z(}_hh'
    'v5P^#?mlzEG3__UCKpG%*cAN|CdbzkQLaeu&p)m6Uy4bI4E;WWoV|W+g1(&Xv!r;y89;8SFWF6NX^^T<I4?E;WO-kKtmm-%vO6@D4f9aV*C6wX'
    'Ui~Zdo7{RaD<s&$nGwSp?|xuQmms0{L+i_huQbXv3NGFL`L^obQ>yz?5z?Xm2|U->&%R^~D~=#o5Q2rPCh|vV>5ckbdjxKknmXdcLW&pl-_QW!'
    'V7t>BRE4!wA(m<o9uO;iL`;pTB+e<Ns&CgZ7NT0J6@e3NxfD5&zZGO$MoA%kG9ri8@Gf$(8y`U_H9jIqq}VY)(RG$wWv`i*w~STMP-6KByv#sJ'
    'ZPJaGF^jD@l+1hB>$wPp_`HZgW4E`-?6K|I3KSjLZY-5mI;%cR`z(v9DEhuEM9*?ogBf|F2bSuF%b@9EPG+$hFaYFcF~NQGF{@M})Lll)WTj-#'
    'iZoikB5a#IuQH35B3E73Drj=y;<g%ymTKwH^tU(VO2JZjYW4foEF|NMR4f8Gxrpv|&5AWMxZ(&iiFHQi(kSC1qn_Ox)ChMy{IFD<0yyDWbC$x;'
    'k<Ql3ZCk~uKdu1Zc8V2zLAqPxaadAEEpKG45IFMhb8TyCbN%D4nKQJE$t`at+{#22Tv|dD<&^ij1$#1NQpr&(qyGaGgdGkl!2eN^Q6wTPa>Csf'
    '(|h|0(ODOj5u9a)0iqbgN9o-B_>&lpFIatzKVJw{*&`zqn=_XJtKQa)!(v<l0>1Kg*`&zdM^?me{M%)77-w1smQOP1bk;?ps(?eab!fdDn~%Ya'
    '<|2Ji#EqrhM<(PdrCWD^8fP_59ZLrCxvgX!SC^nf@!OXr=;gFbZYKq1qMibDpw(LiK_gw~_%bCn$zQQeB4JCW{g>eh)MFn|`iQCGxzr@Ya~B?j'
    'B)+As1u!a5{E&k^SwYpV1k@~k2@@zgnb6bYi0L$9BCwx2W=ePb_tPL;n;at&CZrlvP|+m6zu!Gy!XJi4m^Ih%WCMcA?$G2FwkfLm=->b3NSyX-'
    'k_%duj%`!&xvXnYrI!<~$$`AjOzB+UMs<-D!sbbO!Sd2EPGnpaY1exc3SZ7C!PDhn4d82+)yd70Ihhs>F^5FC=QL9j5>;(E0W~nV9zf<feM7m?'
    'DQ*&`jKERmGGVAdfv6cbK+(|RQAr^zX;tYs{vti1i7$JT_)4CRcT^_(oJqqR)laU~>w{kw-m})VLmpk@#w&)yBncI@8CaE<bE;05cugZCNvOE*'
    'yfpMC=l3&f><L59a3pSlwpcI^-#Nc=zTK8v0T6VYT+uOuDhdZpqT+V2&lc>%XMY}pPyTGCdn9oo2Z#*if)&E7s3Ib#t|E#aJ=^fik64p~0l1J_'
    '=P@v#DSV%X4Z0>zG*Ohy2v~p^ysQ~mj|dTIR&wqnG;}yhnx)AR+#h=Z^i7gh`SlO@@eXCl_TFIFAE4oWU1=6+vL|UFBdV^9OSZN;v6{|Z+NJrE'
    '06o{NutUrsuMTM|x?^ZG7<u*kRI%qJT(1pBIECnMlkF=KUP}b<05xN&z_BUsu#yOqC=4%78hU+`b$0uPr7De6(|Vy>p&Wy7KKlRrW4F~ZfT4#-'
    'D!tK&z&l2loA5h|fhSLH%5>25mnl-+h0j-<oM}5H%_Joh6jZAhJfQ_IN$QYD!V!1ySqDkCU-G-7HdsS4jnUMgE|pkvkfct=Rcldem+^H)sa<Sb'
    'Mb+K2Ua+A(_De47i{#b5vd7Y~${@m-N<eZQ!9;Yvjg5@UKOHkk3Vo1knD3JAz8*-o&C3!VL%ZJ}mAux~Qdq(c?aKC6a#8`en2cBMqG`5H%1&Jz'
    '|8{sQN?l?cEP8whC-*3<R7gLo<tULnpmtR8d7Pm<vCC|)jUR*5kJN)Jcfd1?Y7B2nN7va8#nd7)w{}exUE%PS{o_q$Dr*r06!_*DGQ7<t#~6$('
    'C12`^=kz2EZ3@>d_HJi)Ih}^2)Gy3)wb~|gqT$Hos5}ODz=|`&$o}~9l~DESmn->;4mDb_@k>L6JpP_JnW#O|%HgJS_FvHl%f<x@al8ssF^f;F'
    'LW7zKmfh*K>#5#HDvq8O69FKC4KfTi#1iI&&C)|tpUKhbqafYJ%J{y$a`q+pe5Ippz~Af|)VE#-AXUl|P5^IeT~pMaR8L(~7e?Rc(tn?Fu04(z'
    'ra6n#6ig2fXGR_R&+uz8UpqF(x!W~@cBle8@WYPzZtF2Il}Q1y9&5oU+^O<isp~1+cnI)Q!Bg6T3t2K4c85d)qA`$kbPc_fCD+o*yl$a>ZwOgJ'
    'q$Ik(x`q}Y4J3*fCy1zrU<sJ~6|EbLd7uV{oa-J`NCTtIIn8@nXDd}1EjX$7R*5nXax+gu1=>zuh?z)0l*sIQdDbeNX)zX)&6Fx6eR|kFUKJR('
    '_ue*|kkUyXoF2|{WP6zGo+ucEvwJ!#rVRGYu4|s%XU+2bjC_un@a}nc+C9QerG<4%V%CD^&LYm`ivBaup{N~|Gm%D18OTj<qj(AH`_e=(sUWGE'
    '0p<VvbF5{N3p`bWu8UPIHbC5;kV%8I%6qP8PQ=-Gx!rdEbWSoWTuK*tacFB@wDm)<SX8vJZe5w!lwol=7MYJ2wC63+r<HOOQd!IP9)dTOWb@E0'
    'o6GQHx-4W=NT#hSiTpb-3$&po_a6YJ?2n%fF8sPnxr6Bg)5sT_@$>d^uX%|;8{Q^58@p!H9Vz296)qC`_@I(TQW~VYS7KZ&+Z&PtOry&xiD3l?'
    'iCVOY^mGC7u}qu>Z<9*t;Zc>2)J^>5GOY`}33!RRl_EGvDJL$iII?R^vXpC$;fMm+JS$!foFYK0TAh+O*18f@i55}lTeYNya`9!?-1IfHG%+Tv'
    '>lb)ck-bUWW2N^BOgof))9IPVrYHiDW-5k-H}tgnTsmotT~`}2<-ik;l6BrYd_L{&k$grK=u0Y?g7V_y3tUCplQg)79U^+S+vYt`8-uJ+X~6=F'
    'yLnzyG-9f3ENC-diT+MwbSa*%8d0iAb4;^OiV+MsckmF1vWEid*EE=wuE=)85q7A}#kXCW5=T>52y>#}UDniU5rMC+YSjBEn)O(Z3&hlTIe6GX'
    'jt5=*^amaL7HwMZq*A2o)mwRaw!VcbE${ow=?e&!i?k4}TkWni?=E{}vnU3a@~l9p?{F&Y#3Oy9amQ{JYC~Au3i{cC6!wB|nl>n78$380O4wu('
    'MVw{iz9-%?X>dpzA7Z>q<k1@OeP5|Ul3-V=*c&$QHn&)>J!#1P+-d=OB46y<Sght4Z^15`-by!JN=ftpO}>^Y-x-y*sh4kyUQTXVjcc}gZWYR}'
    '4$gidsY=0ed#khr#cuKb4HaKd_D55~>;mMBR8o<zLFp`GZw=T!*E(&`#6-R%Wm`;~%y|bsR|zO&6W#HOF8Z#pT-7RFW{$8-RX2n{@gRD=S_h!u'
    '2Q|rH-k~xNzL>r!Z+R@uW&K+rS13N#D=NL!mu{p-5w{=v@fAN<740RmqdINVGtKy+W|F;WliyW%FG{jj<jWJzvsaTYRsdAcL8_;S+4zu?_DZ=%'
    'jp#2jFVTkhR$_dcTz6Ak_f}<bX$uKEKAWofL;;|zCZ14_E6%1j<)q*;$!8$+a*gY?f3q1|A@qU#5!V*80j{J{%Yas3U7NELCI7u@N-jkBkY<hd'
    '+H78|BeJT?Z16X{$y|>|`aeM3Ll^rVWF@VY4ASPXgEmgw9edpaL8$7HZS?93|FP;4f66UR|905>o$bDSA&6nYemjKtB@VHnne$NavvW(=YD}(g'
    'stjTcVYZnf6vc^@5awvJ98*KCa0X7pw>D)<3y@~v;>~)M7YsoK0yk5P0A!7YF=j8hZ$zz4^rY`L70lsE?#S5{^DpEug)aCjg|xZ6SOw;@{MVLB'
    ';NAgFhL|$Ncg}1xQB=Utf?Dy&-lAQvsV0#nsx(2i1r)ymFVN~-$|Nge1F8l?2D2MxDRi(iPl6mO>ylk6OB7Kqnqh$8IaI`)*#zMCrT{7e>Y26h'
    '!*9Vnvt+Gq?5u@5tS0^bjW$xX-=Yyl;ioGghi<v@gpN27+?A#|o(7H@`KSH%0`*-J$I4XNW_C+T09RIO{?If}afA&+(l|Skk|VN*S~AB>v(!e`'
    'h|<)Iv@s)@;?B)xrCxBx@7Zk2Qocwu00VE5KYhCt6lSKhEZeAIa2A*g8<|UwA>mRIpcmMXSgr;rH7{VLu?_tZj?zN~w07RwY)=P*Y;Qm7_WKaV'
    '1(K5oLoM||ft8ugQ~F=C4V#VhQDi!1KX-(!E*c|VsBTb1zGX7>KwEn<-jHo>xUCyW3!*=t{$$pmV@yMq0ZpN_W;bdcc{dJ;cSw%aMb*_e2JI#*'
    'uFsM<YIv1OEXT<kG2nU?a3$Bwid|362{{<&5=RxjyC|lza^AmKPfI_$I8YaJiUi^xNN32O-at}~jEeATtTeP0<pNyrQR<YIwsF$0CaQr+a{2BZ'
    'V=~xkF1IMe?O-sZP|<|eVy@TGtt-B_^2>J8+w?s>Q4+)g?5w(e4|1|`zI}OqH4U5bb)$K4OSsqNWB-P{UqzuBx)*7)yr0#(ik8J)$t&r&tPwQR'
    '4_C`ne`G3!?0N+(xZzVLW4S_c28<P)##5B5@sjkM*4<XKU3#SD3nYH!84}K%I(HG&4|FPbXOzaEvbJO=Hi6x(7^8t>;VGtsT3BSQe@*iJmJ*!)'
    'EyW%|fz7Bh8FLlN@`@c>i8>PCLZS#t<^j1V^~F>m6go9f2Z=opj$5e_to_t!2q;-|J`s+Hi_$-@w<n@<Q0~d|oZOLZ+wB_jPvByulYZ@~`t@|?'
    'D4wK>c<f7P=jB5wgKXWJzA;xt$#Z#$&$>2!P<AJ8j3SLqd-h(hvm|A%)@R#QZMnafA15#G>B(|^)mAYmAQh>pd}JWel3EE?ny;=0Ns$aIoO7m1'
    'LPUeuSqD<HSUcFNVx7_XFXd`|YaxK_ml~iCW{X=>W&7vjMJ#t@cREA2$fgo0uf_(Ihid(@C-`O={b}O*Sr-IaYky5tdIW*;CHVY(tmHaUy%B?`'
    'Xi^m5;C%Vo^pPU|zE=F$Yf+H+90a5p7<!m<ouula@u~<BItVSl5}n+|Zp*P`!*eG}UtUvG15t1W5W5XRDeELF?oD8H4Il76+xxnJJmJ1jk<JmD'
    '!k%u0jt<&1XREAL2d{Te1PG}bXF_2yy}8PiSySQ1%X$hml~>mVCxYbsspuqai7mLi>{HpxpV&EBfe1C)@ixlnrvw&cH_hV}^7kka2BC+=nZxkR'
    '!9=*1fvL%GMF9i;EDJbnLf-)Q7<EQ~^irkuTBy}Xwkk(t;}kgFhR%@<z2atEY>pdn(jEz-_D`!gEg#56<w*du?e06ALYuL}%{oj5#cs&$9%*v<'
    'q0mp2A86Ep6Q2A)U31B-f&*$Zo}8tLa45twY=s*JRBZ@Q#UZW@ppabGU2?2~j8^cgUX(-u3qrS_l_`xwsex&k&+=&|j`SZ>0h0Ue>jhw;CPKMU'
    'E^nGt6m*~Xv&+P&+Psd9S6uF@Ex?@ACG0dq13{o#K-~qVK0Hq;v5cOfjj9c@L76hJj=vSfEvM$xE$;?wGrXEHv#pYU<MywxK?SzWl+<M$InRN{'
    'V)FpbM_Fb^6zeWk1Jn#8-rD}q>}VY-9OZ`D|8T_A_gKl;<XbAA0+wPbNvVIUB8fzO4rU4sqNvj!)iBN#kj>3pO1{k;Ed50S*&8dgEA!j<YOW4~'
    'qp0}eiy4iC9thuj`<))O{BlwGWi;pvZKq?d6Wx=Ai1{{w;>BaE7?qRUkSu{nA-|4Zl%%g$)wTJHToj=aLzvnvs+&CXm;$hwxK;i)4XpN?Ua*a-'
    'x&d*+smjeD7aPu&!cjV_adw{0i^_+VJuag9mMxVDWwaErfQ>3q4zqeeQPoW=F-0E?i0KV$L^z_%U{|vIB^1t8qOxywdy}I4Ur{zn3-ih;lZIzK'
    'i6I1}zM`|&I=eS&f9Jf-s-9r9&Sjl>Q^z))Q(_vK3Wjc0O6Z7aFf1#IV#Re9bII$n;Q%m>!~@J4$tG-VP!5kUdDo|+SBG}bu3^8D74qZ?Q3Bt)'
    '^^&>cK^bUPDQt5~b}Ei|3>Gx6IW{2`6da*2mEAQ51>4MUrUb!lRQe^USO+RpJrPzJ65#c4|FHdDn>Nr>fkm{TggDMr0roTELCehWN^1nJKHkoy'
    'eG6RDGh9wU6y;j>^oZEyMm5Fvx*8GX4R2;R!V^h<>mD)0CB!%eED%Ds)D@5xHW&>{{A5?>MQO`?CDE|l<8H{!QDO0WXRL1M!kYjN=^>xUfRUK0'
    '$g#p~8DX%xHB=KLl|OM4MBHEapb}KPIBoz7J^a!{3fRigO_nJFW@{{bH=J{bBXbjazkVGL9M&<YjF?ItYi3SpuD)lY^cOO@Qi>F$R4>`Ns1R9B'
    'hOU;ibCXDO;s!PDe_cF@*{4w0Q8#Rg;t0=iTbx}A+|ICfQ&a3oxMRh#xKS?Ln^#oixd`@HMm6f@R@w*SJp`=DyKmCnZdX#S;zVN_dw*7aQWZQu'
    '`5~AQT8Qe06sMJ}@lCh4Ph$nS`{d#DO#`Gx{ru!B+NMuz2uW8OD40aPRYCfzYV4A;@vl|ZKvDUWNki?^F@N4wF`!n*Skm(U{y)g}y8i'
)))
# Explicit identifiers: do not replace historical RICs with surviving acquirers.
# Start with the two companies already checked on the university account.

# metric -> (field, fiscal-period-date property, value type).
# Modern TR.F.* .date is the fiscal period end, not the publication date.
ANNUAL_FIELDS = {
    "total_assets": ("TR.TotalAssetsReported", "periodenddate", "number"),
    "revenue": ("TR.TotalRevenue", "periodenddate", "number"),
    "cost_of_sales_provider": ("TR.CostofRevenueTotal", "periodenddate", "number"),
    "sga": ("TR.SgaExpenseTotal", "periodenddate", "number"),
    "interest_expense_provider": ("TR.InterestExpense", "periodenddate", "number"),
    "common_equity_provider": ("TR.F.ShHoldEqCom", "date", "number"),
    "total_equity_provider": ("TR.TotalEquity", "periodenddate", "number"),
    "minority_interest_provider": ("TR.F.MinIntr", "date", "number"),
    "income_announcement": ("TR.ISOriginalAnnouncementDate", "periodenddate", "date"),
    "balance_announcement": ("TR.BSOriginalAnnouncementDate", "periodenddate", "date"),
}
OBS_COLUMNS = [
    "ticker", "ric", "metric", "field", "requested_fiscal_year", "period_end",
    "observation_date", "numeric_value", "announcement_date", "raw_value",
    "currency_requested", "reporting_state_requested", "date_status",
    "source_row", "request_key",
]


def duration(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"


def default_output():
    for parent in Path(__file__).resolve().parents:
        if (parent / "src/Data_System/config.py").is_file():
            return parent / "Data/Fama and french/LSEG_Company_Data"
    return Path(__file__).resolve().parent / "lseg_company_data_output"


def save_text(path, content):
    """An open Excel report must not destroy an otherwise completed download."""
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(content, encoding="utf-8-sig" if path.suffix == ".csv" else "utf-8")
    try:
        os.replace(temporary, path)
    except PermissionError:
        path = path.with_name(path.stem + "_latest_" + uuid.uuid4().hex[:8] + path.suffix)
        os.replace(temporary, path)
        print(f"Report locked; saved {path.name} instead.", flush=True)
    return path


def load_companies(args):
    if args.input:
        frame = pd.read_csv(args.input, dtype=str, keep_default_na=False)
        frame.columns = frame.columns.str.strip().str.lower()
        for target, alternate in (("ric", "lseg_ric"), ("isin", "lseg_isin")):
            if target not in frame and alternate in frame:
                frame[target] = frame[alternate]
        if "ticker" not in frame:
            raise ValueError("Mapping requires ticker; unresolved RICs will be searched.")
    else:
        frame = pd.DataFrame(EMBEDDED_UNIVERSE, columns=["ticker", "ric", "company", "isin", "first_membership_date", "last_membership_date"])
    for column in ("ticker", "ric", "company", "isin"):
        if column not in frame:
            frame[column] = ""
        frame[column] = frame[column].str.strip()
    rejected = frame.loc[frame.ticker.eq("")].copy()
    frame = frame.loc[~frame.index.isin(rejected.index)].drop_duplicates(["ticker", "ric"])
    if frame.ticker.duplicated().any():
        raise ValueError("Mapping has multiple RICs for a ticker; resolve these identities first.")
    if args.limit is not None:
        frame = frame.head(args.limit)
    if frame.empty:
        raise ValueError("No company identifiers selected.")
    return frame.reset_index(drop=True), rejected


def resolve_identifiers(ld, companies, root, refresh):
    """Search exact US stock symbols, retaining ambiguous identities for review."""
    path = root / "identifier_search.json"
    cache = {} if refresh or not path.exists() else json.loads(path.read_text(encoding="utf-8"))
    result, diagnostics = [], []
    missing = companies.ric.eq("")
    count = int(missing.sum())
    started = time.perf_counter()
    fields = ["RIC", "DocumentTitle", "TickerSymbol", "ISIN", "IssueISIN", "IssueDate", "RetireDate", "IsPrimaryIssueRIC"]
    if count:
        # Use only properties advertised by this account's EquityQuotes view.
        # This handles both transposed and row-oriented metadata, as in the
        # earlier successful historical-symbol search script.
        try:
            from lseg.data.content import search as search_content
            metadata = search_content.metadata.Definition(view=search_content.Views.EQUITY_QUOTES).get_data().data.df
            names = set()
            def collect(value):
                if isinstance(value, str):
                    names.add(value)
                elif isinstance(value, dict):
                    for key, item in value.items():
                        collect(key)
                        collect(item)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        collect(item)
            collect(metadata.index.tolist())
            collect(metadata.columns.tolist())
            collect(metadata.to_numpy(dtype=object).tolist())
            selected = [field for field in fields if field in names]
            if {"RIC", "DocumentTitle", "TickerSymbol"}.issubset(selected):
                fields = selected
        except Exception as error:
            print(f"Search metadata unavailable: {type(error).__name__}: {error}. Trying explicit stock properties.", flush=True)
    for index, company in enumerate(companies.to_dict("records"), 1):
        if company["ric"]:
            company["mapping_status"] = "EXISTING_MAPPING"
            result.append(company)
            continue
        ticker = company["ticker"]
        record = cache.get(ticker)
        if record is None or record.get("error"):
            escaped = ticker.replace("'", "''")
            variant = escaped.replace("-", ".")
            filters = (
                "BusinessEntity eq 'QUOTExEQUITY' and ExchangeCountry eq 'USA' "
                "and (RCSAssetCategoryLeaf eq 'Ordinary Share' "
                "or RCSAssetCategoryLeaf eq 'American Depository Receipt' "
                "or RCSAssetCategoryLeaf eq 'Depository Receipt') "
                f"and (TickerSymbol xeq '{escaped}' or TickerSymbol xeq '{variant}')"
            )
            try:
                frame = ld.discovery.search(
                    view=ld.discovery.Views.EQUITY_QUOTES, filter=filters,
                    select=",".join(fields), top=100)
                records = [] if frame is None else json.loads(frame.to_json(orient="records", date_format="iso"))
                if not records and company.get("company"):
                    frame = ld.discovery.search(
                        view=ld.discovery.Views.EQUITY_QUOTES, query=company["company"],
                        filter=filters.split("and (TickerSymbol", 1)[0].strip(),
                        select=",".join(fields), top=100)
                    records = [] if frame is None else json.loads(frame.to_json(orient="records", date_format="iso"))
                record = {"records": records, "error": "", "capped": len(records) >= 100}
            except Exception as error:
                record = {"records": [], "error": f"{type(error).__name__}: {error}", "capped": False}
            cache[ticker] = record
            save_text(path, json.dumps(cache, ensure_ascii=False, indent=2))
            time.sleep(0.15)
        candidates = []
        for candidate in record["records"]:
            issued = iso_date(candidate.get("IssueDate"))
            retired = iso_date(candidate.get("RetireDate"))
            first = company.get("first_membership_date", "")
            last = company.get("last_membership_date", "")
            if (issued and last and issued > last) or (retired and first and retired < first):
                continue
            if not candidate.get("RIC"):
                continue
            candidates.append(candidate)
        # Venue quotes of the same ISIN form one security; unrelated same-symbol
        # securities never get collapsed into a single guessed company.
        groups = {}
        for candidate in candidates:
            isin = candidate.get("ISIN") or candidate.get("IssueISIN") or candidate["RIC"]
            groups.setdefault(isin, []).append(candidate)
        status = "IDENTITY_REVIEW" if groups else "NOT_FOUND"
        if len(groups) == 1 and not record["error"] and not record["capped"]:
            entries = next(iter(groups.values()))
            entries.sort(key=lambda r: (str(r.get("IsPrimaryIssueRIC", "")).lower() != "true", str(r["RIC"])))
            chosen = entries[0]
            stopwords = {"inc", "corp", "corporation", "company", "co", "the", "ltd", "plc", "holdings", "group", "common", "stock", "class"}
            def words(text):
                return {w for w in re.findall(r"[a-z0-9]+", str(text).lower()) if len(w) >= 3 and w not in stopwords}
            expected = words(company.get("company", ""))
            returned = words(chosen.get("DocumentTitle", ""))
            # A unique same-symbol result can still be a different issuer.
            if expected and not expected.intersection(returned):
                status = "COMPANY_NAME_MISMATCH_REVIEW"
            else:
                company["ric"] = chosen["RIC"]
                company["isin"] = chosen.get("ISIN") or chosen.get("IssueISIN") or ""
                company["provider_company"] = chosen.get("DocumentTitle", "")
                # Extraction candidates remain explicitly unverified, even if unique.
                status = "UNIQUE_SECURITY_CANDIDATE_REVIEW"
                company["mapping_status"] = status
                result.append(company)
        if record["error"]:
            status = "SEARCH_ERROR"
        diagnostics.append({**company, "mapping_status": status, "candidate_securities": len(groups),
                            "search_error": record["error"], "capped": record["capped"]})
        print(f"Identifiers: {len(diagnostics)}/{count} {ticker}: {status} | elapsed {duration(time.perf_counter() - started)}", flush=True)
        save_text(root / "identifier_report.csv", pd.DataFrame(diagnostics).to_csv(index=False))
    frame = pd.DataFrame(result)
    if frame.empty:
        raise RuntimeError("No identifiers available. See identifier_report.csv and identifier_search.json.")
    # Renames can legitimately share a RIC. Keep the original ticker labels and
    # flag these links; issuer/share-class deduplication belongs before modelling.
    duplicates = frame.ric.duplicated(keep=False)
    save_text(root / "duplicate_identifiers_review.csv", frame.loc[duplicates].to_csv(index=False))
    frame.loc[duplicates, "mapping_status"] = "SHARED_RIC_REVIEW"
    return frame.reset_index(drop=True)


def column_key(column):
    # HeaderType.NAME may include inline field parameters and .value.
    name = str(column).split("|")[0].strip().lower()
    name = re.sub(r"\([^)]*\)", "", name)
    return name.removesuffix(".value")


def find_column(frame, name):
    matches = [i for i, column in enumerate(frame.columns) if column_key(column) == name.lower()]
    return matches[0] if len(matches) == 1 else None


def iso_date(value):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return ""
    # Numeric 2018 must not be interpreted as nanoseconds since 1970.
    if isinstance(value, (int, float)):
        return ""
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.date().isoformat()


def parse_observations(frame, companies, metric, field, date_property, kind, year, key):
    """Keep the field's own period date; never align different metrics by row number."""
    instrument = find_column(frame, "instrument")
    value_column = find_column(frame, field)
    date_column = find_column(frame, field + "." + date_property)
    if instrument is None or value_column is None:
        return [], "RAW_DATA_UNPARSED"
    by_ric = companies.groupby("ric")["ticker"].agg(list).to_dict()
    rows = []
    for source_row, values in enumerate(frame.itertuples(index=False, name=None)):
        ric, value = str(values[instrument]), values[value_column]
        if ric not in by_ric or pd.isna(value) or str(value).strip() == "":
            continue
        date = iso_date(values[date_column]) if date_column is not None else ""
        numeric = pd.to_numeric(value, errors="coerce") if kind == "number" else None
        announcement = iso_date(value) if kind == "date" else ""
        if (kind == "number" and pd.isna(numeric)) or (kind == "date" and not announcement):
            continue
        rows.append({
            "ticker": by_ric[ric][0], "ric": ric, "metric": metric, "field": field,
            "requested_fiscal_year": year, "period_end": date if year else "",
            "observation_date": date if not year else "", "numeric_value": numeric,
            "announcement_date": announcement, "raw_value": str(value),
            "currency_requested": "USD" if kind == "number" else "",
            "reporting_state_requested": "Orig" if year else "",
            "date_status": "DATED" if date else "MISSING_DATE_REVIEW",
            "source_row": source_row, "request_key": key,
        })
        for alias in by_ric[ric][1:]:
            rows.append({**rows[-1], "ticker": alias})
    if not rows:
        return [], "NO_USABLE_VALUES"
    status = "EXTRACTED" if all(r["date_status"] == "DATED" for r in rows) else "EXTRACTED_DATE_REVIEW"
    return rows, status


class Downloader:
    def __init__(self, ld, root, refresh, total):
        self.ld, self.root, self.refresh, self.total = ld, root, refresh, total
        self.started = time.perf_counter()
        self.calls = 0
        self.network_seconds = 0.0
        self.reports, self.observations, self.identities = [], [], []
        self.db = sqlite3.connect(root / "raw_responses.sqlite")
        self.db.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, request TEXT, data TEXT, retrieved_at TEXT)")
        # Confirmed from the installed 2.1.1 public get_data signature.
        if "header_type" not in inspect.signature(ld.get_data).parameters:
            raise RuntimeError("This file expects ld.get_data(header_type=...). Use the verified lseg-data 2.1.1 environment.")

    def request(self, rics, fields, parameters, label):
        request = {"universe": list(rics), "fields": fields, "parameters": parameters}
        encoded = json.dumps(request, sort_keys=True)
        key = hashlib.sha256((VERSION + encoded).encode()).hexdigest()
        cached = None if self.refresh else self.db.execute("SELECT data FROM responses WHERE key=?", (key,)).fetchone()
        before = time.perf_counter()
        report = {"request_key": key, "label": label, "source": "CACHE" if cached else "SDK",
                  "status": "", "rows": 0, "usable_observations": 0, "error": "",
                  "universe": json.dumps(list(rics)), "fields": json.dumps(fields),
                  "parameters": json.dumps(parameters, sort_keys=True)}
        number = len(self.reports) + 1
        print(f"[{number}/{self.total}] {label} ({report['source']}) ...", flush=True)
        try:
            if cached:
                frame = pd.read_json(io.StringIO(cached[0]), orient="split", convert_dates=False)
            else:
                done = threading.Event()
                def heartbeat():
                    while not done.wait(15):
                        print(f"  waiting for LSEG: {label}, {duration(time.perf_counter() - before)}", flush=True)
                worker = threading.Thread(target=heartbeat, daemon=True)
                worker.start()
                self.calls += 1
                try:
                    frame = self.ld.get_data(**request, header_type=self.ld.HeaderType.NAME)
                finally:
                    done.set()
                    worker.join()
                    self.network_seconds += time.perf_counter() - before
                if not isinstance(frame, pd.DataFrame):
                    raise TypeError(f"Expected DataFrame, received {type(frame).__name__}")
                # Save before parsing. An unexpected column cannot erase downloaded data.
                if not frame.empty:
                    payload = frame.to_json(orient="split", date_format="iso", default_handler=str)
                    self.db.execute("INSERT OR REPLACE INTO responses VALUES (?,?,?,?)",
                                    (key, encoded, payload, pd.Timestamp.now(tz="UTC").isoformat()))
                    self.db.commit()
            report["rows"] = len(frame)
            report["status"] = "RAW_SAVED" if not frame.empty else "EMPTY_RESPONSE"
        except Exception as error:
            frame = pd.DataFrame()
            report["status"] = "REQUEST_ERROR"
            report["error"] = f"{type(error).__name__}: {error}"
            with (self.root / "errors.log").open("a", encoding="utf-8") as stream:
                stream.write(f"\n{label}\n{encoded}\n{traceback.format_exc()}\n")
            print("  " + report["error"], flush=True)
        report["seconds"] = round(time.perf_counter() - before, 3)
        self.reports.append(report)
        return frame, key, report

    def progress(self, report):
        elapsed = duration(time.perf_counter() - self.started)
        remaining = self.total - len(self.reports)
        # Upper estimate: treats all remaining jobs as new SDK calls, even if cached.
        eta = duration(remaining * self.network_seconds / self.calls) if self.calls >= 3 else "estimating"
        print(f"  {report['status']}: {report['usable_observations']} values | elapsed {elapsed} | ETA <=~{eta}", flush=True)

    def save(self, companies, finished):
        observations = pd.DataFrame(self.observations, columns=OBS_COLUMNS)
        save_text(self.root / "observations.csv", observations.to_csv(index=False))
        reports = pd.DataFrame(self.reports)
        save_text(self.root / "request_report.csv", reports.to_csv(index=False))
        if self.identities:
            save_text(self.root / "identities.csv", pd.concat(self.identities, ignore_index=True).to_csv(index=False))
        coverage = []
        grouped = {key: group for key, group in observations.groupby(["ticker", "metric"], sort=False)}
        empty = observations.iloc[:0]
        for company in companies.to_dict("records"):
            for metric in list(ANNUAL_FIELDS) + ["market_cap"]:
                found = grouped.get((company["ticker"], metric), empty)
                dates = found.observation_date if metric == "market_cap" else found.period_end
                dated = dates.loc[dates.ne("")]
                coverage.append({"ticker": company["ticker"], "ric": company["ric"], "metric": metric,
                                 "observations": len(found), "dated_observations": len(dated),
                                 "fiscal_labels_with_values": found.requested_fiscal_year.nunique() if metric != "market_cap" else 0,
                                 "first_date": dated.min() if len(dated) else "",
                                 "last_date": dated.max() if len(dated) else ""})
        save_text(self.root / "coverage.csv", pd.DataFrame(coverage).to_csv(index=False))
        statuses = reports.status.value_counts().to_dict() if not reports.empty else {}
        notes = ["# LSEG company data extraction", "",
                 f"- Version: `{VERSION}`", f"- Companies selected: {len(companies)}",
                 f"- Completed request jobs: {len(reports)}/{self.total}",
                 f"- Finished plan: {finished}", f"- New SDK calls invoked: {self.calls}",
                 f"- Extracted observations: {len(observations)}",
                 f"- Elapsed: {duration(time.perf_counter() - self.started)}", "",
                 "## Request status", "", "| Status | Requests |", "|---|---:|",
                 *[f"| {status} | {count} |" for status, count in statuses.items()], "",
                 "## Files", "",
                 "- observations.csv: source accounting amounts, dates and monthly market cap.",
                 "- coverage.csv: counts and date ranges per company and metric.",
                 "- identities.csv: returned provider identities; compare with selected_companies.csv.",
                 "- request_report.csv: exact fields, parameters, cache source and errors.",
                 "- raw_responses.sqlite: original response tables and retrieval timestamps.",
                 "- errors.log: full exceptions, if any.", "",
                 "## Interpretation", "",
                 "These are extraction candidates, not finished Fama-French inputs. Coverage counts",
                 "are not membership-day coverage percentages. Check company identities, actual fiscal",
                 "period dates, publication dates, currency/scaling, equity/expense definitions and",
                 "duplicate records before modelling. Missing expenses are not assumed zero.",
                 "Monthly market-cap dates are preserved as returned; month-end coverage is not assumed.",
                 "Orig is a requested reporting state, not a certification of point-in-time availability.",
                 "Company capitalization can include multiple share classes; avoid double counting.",
                 "This file does not download market-factor returns or an FF-compatible risk-free series.",
                 "No price dataset, existing SEC file, factor output or main pipeline was changed."]
        save_text(self.root / "report.md", "\n".join(notes) + "\n")


def run(args):
    import lseg.data as ld

    companies, rejected = load_companies(args)
    root = (args.output or default_output()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    save_text(root / "selected_companies.csv", companies.to_csv(index=False))
    save_text(root / "requested_universe.csv", companies.to_csv(index=False))
    save_text(root / "unmapped_input.csv", rejected.to_csv(index=False))
    print(f"LSEG COMPANY DATA {VERSION}\nScript: {Path(__file__).resolve()}\nPython: {sys.executable}", flush=True)
    print(f"LSEG: {getattr(ld, '__version__', 'unknown')}\nOutput: {root}", flush=True)
    print(f"{'LIMITED INPUT' if args.limit is not None else 'FULL UNIVERSE'}: {len(companies)} companies; FY{args.first_year}-FY{args.last_year}", flush=True)
    if len(rejected):
        print(f"WARNING: {len(rejected)} input rows have no ticker/RIC; see unmapped_input.csv.", flush=True)
    print("Opening signed-in Workspace session...", flush=True)
    downloader = None
    finished = False
    try:
        ld.open_session()
        # EXACTLY the successful request. Do not turn an import/session failure
        # into 200 empty-response messages. No historical prices are requested.
        print("Connection check: CELG.O^K19 revenue FY2018 (previously returned USD 15,281,000,000)...", flush=True)
        probe = ld.get_data(universe=["CELG.O^K19"], fields=["TR.TotalRevenue"], parameters={"Period": "FY2018"})
        print(probe, flush=True)
        if not isinstance(probe, pd.DataFrame) or probe.empty:
            raise RuntimeError("The previously successful CELG request returned no rows; stopping before the extraction plan.")
        values = probe.drop(columns=[c for c in probe if str(c).lower() == "instrument"], errors="ignore")
        numeric = values.apply(pd.to_numeric, errors="coerce")
        if not numeric.notna().any().any():
            raise RuntimeError("CELG connection check has no numeric revenue; inspect the printed response.")
        save_text(root / "connection_check.csv", probe.to_csv(index=False))
        companies = resolve_identifiers(ld, companies, root, args.refresh)
        save_text(root / "selected_companies.csv", companies.to_csv(index=False))
        batches = [companies.iloc[i:i + BATCH_SIZE] for i in range(0, len(companies), BATCH_SIZE)]
        total = len(batches) * (2 + args.last_year - args.first_year + 1)
        print(f"Extracting {len(companies)} mapped companies in {total} batched jobs. Unresolved identities remain in identifier_report.csv.", flush=True)
        downloader = Downloader(ld, root, args.refresh, total)
        for batch_number, batch in enumerate(batches, 1):
            rics = list(dict.fromkeys(batch.ric))
            frame, key, report = downloader.request(rics, ["TR.CommonName", "TR.ISIN"], {}, f"batch {batch_number}: identity")
            if not frame.empty:
                identity = frame.copy()
                identity["request_key"] = key
                downloader.identities.append(identity)
            downloader.progress(report)
            # First request FY2018, where real revenue was already observed.
            years = list(range(args.first_year, args.last_year + 1))
            if 2018 in years:
                years.remove(2018)
                years.insert(0, 2018)
            for year in years:
                parameters = {"Period": f"FY{year}", "ReportingState": "Orig", "Curn": "USD", "Scale": 0}
                fields = [item for field, date_property, kind in ANNUAL_FIELDS.values()
                          for item in (field, field + "." + date_property)]
                frame, key, report = downloader.request(rics, fields, parameters, f"batch {batch_number}: FY{year} / annual accounting")
                extracted = []
                if not frame.empty:
                    for metric, (field, date_property, kind) in ANNUAL_FIELDS.items():
                        rows, status = parse_observations(frame, batch, metric, field, date_property, kind, year, key)
                        extracted.extend(rows)
                # Retry each field only when the combined request failed or
                # yielded no usable accounting values. No silent definition swap.
                if not extracted:
                    downloader.total += len(ANNUAL_FIELDS)
                    for metric, (field, date_property, kind) in ANNUAL_FIELDS.items():
                        single, single_key, single_report = downloader.request(
                            rics, [field, field + "." + date_property], parameters,
                            f"batch {batch_number}: FY{year} / fallback {metric}")
                        if not single.empty:
                            rows, single_report["status"] = parse_observations(
                                single, batch, metric, field, date_property, kind, year, single_key)
                            extracted.extend(rows)
                            single_report["usable_observations"] = len(rows)
                        downloader.progress(single_report)
                downloader.observations.extend(extracted)
                report["usable_observations"] = len(extracted)
                if extracted:
                    report["status"] = "EXTRACTED" if all(r["date_status"] == "DATED" for r in extracted) else "EXTRACTED_DATE_REVIEW"
                downloader.progress(report)
                # If added parameters/fields fail, preserve diagnostics and stop
                # after ten requests, rather than running the entire dead plan.
                if batch_number == 1 and year == years[0]:
                    core = {"total_assets", "revenue", "common_equity_provider"}
                    if not any(r["metric"] in core for r in downloader.observations):
                        raise RuntimeError("First fiscal-year batch has no usable core accounting values. Saved exact requests/errors; stopping.")
            frame, key, report = downloader.request(
                rics, ["TR.CompanyMarketCap", "TR.CompanyMarketCap.date"],
                {"SDate": args.market_start, "EDate": args.market_end, "Frq": "M", "Curn": "USD", "Scale": 0},
                f"batch {batch_number}: monthly company market cap")
            if not frame.empty:
                rows, report["status"] = parse_observations(
                    frame, batch, "market_cap", "TR.CompanyMarketCap", "date", "number", None, key)
                downloader.observations.extend(rows)
                report["usable_observations"] = len(rows)
            downloader.progress(report)
            downloader.save(companies, finished=False)
        finished = True
    finally:
        if downloader:
            try:
                downloader.save(companies, finished)
            finally:
                downloader.db.close()
        ld.close_session()
    print(f"Extraction finished. Read {root / 'report.md'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, help="Explicit ticker/RIC mapping CSV")
    parser.add_argument("--all", action="store_true", help="Accepted for compatibility; all companies is already the default")
    parser.add_argument("--limit", type=int, default=None, help="Optional company limit; default processes the full universe")
    parser.add_argument("--first-year", type=int, default=2006)
    parser.add_argument("--last-year", type=int, default=2025)
    parser.add_argument("--market-start", default="2007-12-31")
    parser.add_argument("--market-end", default="2026-08-18")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--refresh", action="store_true", help="Download again instead of reusing nonempty cached responses")
    args = parser.parse_args()
    if (args.limit is not None and args.limit < 1) or args.first_year > args.last_year:
        parser.error("Use a positive limit and first-year <= last-year.")
    if pd.Timestamp(args.market_start) > pd.Timestamp(args.market_end):
        parser.error("market-start must be <= market-end.")
    try:
        run(args)
    except KeyboardInterrupt:
        print("\nInterrupted. Completed raw responses are saved; repeat the same command to resume.", flush=True)
        raise SystemExit(130)
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
