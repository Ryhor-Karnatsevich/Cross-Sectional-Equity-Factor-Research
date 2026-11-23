"""Retry ONLY the failed whole-statement batches, one RIC per SDK request.

Copy this ONE file to the Workspace PC. NO old input folders are needed:
the exact failed requests and ticker labels are embedded in this file.
Run: py -3.12 lseg_1.py
Needs the existing pandas/lseg-data environment and signed-in LSEG Workspace.

No stock prices, identity search, factor calculations or other extraction stages.
Fields and parameters are identical to the failed requests, except each request
contains one RIC. Successful/empty replies are cached; failed calls retry on rerun.
--retry-empty rechecks empty replies. --plan-only shows/saves the embedded plan
without opening LSEG. --output overrides lseg_statement_retry_output beside file.

Raw tables and full provider definitions are retained. Each amount remains a
statement-row candidate, not an approved FF input. A requested FY label is NOT
silently converted into an actual fiscal-period end or a publication date.
"""
import argparse
import base64
import hashlib
import inspect
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
import traceback
import uuid
import zlib
import re
import pandas as pd

VERSION = "2026-11-18-single-ric-statement-retry-v1"
EMBEDDED_PLAN = json.loads(zlib.decompress(base64.b85decode(
    'c-rLMTbJWVawqujQqOhrz%RJC-T)9F5d=UcfFKz$XF><pnVywe+E!`yK}X+x%`>5w-9qF8+h86xXJ%Se#Z-6ye?t&}yP5fa{I>Le'
    '`KNjM$D#jY{Gao`{q_&S_kaKGfBnk<fBE13<F~)f|M$Po|Mtgk|L`Bb{rg}4^1tW5{o4%x{I@tMzSSRRFZ%7j|Nh(Zm-(M2`^SIl'
    'ns52Hr2nV>ujAbQ&w2ji+mFxw+W+(X+wWVSPV>KwfBVb7{_&T8`RkwkA^V^3ul?WP-{KGWPq+U?uJhmi@-NeG|L|M>COyxG|D|UB'
    '*MIrjAAkAl|7ic{|A7C3zg_<Jm;V9(JpK2-{T2T1wLQS!v}6BI@R|3Y|M~lGfBa?qzkd9?{fM&uN6dfy;~&?&KR)rzGH5yai&mkx'
    'C}pG^f+>t<&xGNm2Y-y_VG6w|GK=wME$48IMsGBMzx0bXzy0_B{C!g}z1%)x;eUNU2twg^IDCD&pBZ+S%iE7kGWg~}5DLHS`jH9w'
    '_4%?Zh2HU$eto(%#NKu<^~=|{TSM$^S6)7H4!7I#LZMe(YT#q=v<E>b{OT^ge!F~qKAVHY@9pt%7K#Dj+k?XIdM>^d#m7;2U!M@N'
    'P!P8D;r#6akAA_|C$w284DWIE`u*GW{E>2afc}w&gz=RD-YbP%URN=E|Gqw-4MK7wsTkZqDw6w0_K}E?!M!7+(CZEimJQYryW3?Y'
    '1G}Fg_O^3qqa#4u=n&B|OjAG4Vi}gujEnD$a$3eA@H`>aI7g%M0}<#zje*wl9C-8Wd-EcOaTvw;sbJESAXst`geVk(&TJJ0Xj?_7'
    'elBbk1z1}}xN@#+6$NNpMW}wRY!wAqTScgPc~^XWx;4c9c1`+Yr6rSs17bsgc&guF*F$}MKL|qMSH$V<25Y7V4z~~pLt=P)XJB_D'
    '`TmvJsd8tz`B}stX($+-+58RAHh*#by7K#vui-&3xEKFOL&50E9(sVchmPuZeSExdxQee23O%>BE(64^OI*e`26%52a`CmheLFK)'
    'hK3v@es>Od_cO^F{)55d{nl+G96c2(>4S{ddqxDy?2qslvylB{JRS7YI0M`ii6zv_xGZv-7uaqJd)R9V=g(IF)6<2+LyOH}KaIPV'
    'gt5M!STI5k3O{G+UIM(j7hJ$5g<Z@{GFS|RC=`OHG-j}nnv#6`isamI`1!LrDE!U`7Apr3gF?@h)|mjSbp}`OwS499<+C{`{Hhnb'
    '`W!M?IDM%}{H`ejyDP~vOVy?Yhcy?QgT(JqRIvYh;!uNNvrrh;X?f!C9ke+p{9Nc*2(UU9aOEzC1BWLUn}foytqb_^OF8VhK@<u>'
    'C%QfYw5|_ayPShvzGY{G5Xu*`H>l8uRu10}BQ+S&`<@6q5e>dD!3_UQ2U9PHewcgM{h0L_`Pvh|==yjqyO_f-pUpwxcl-KuHxjp|'
    'J#+Zp*&Gypcc^iRIlOG#H;Y_Q{T^@S*SA|k>}}^zr(lTIDHv!d7=ZT5aW=l1LbG_o>_eyJ;zuF;zX*y6<X{4!7d83AVEj-hVbmm{'
    '-atz2eO_fy96_*<`s)iq6beBXI^9C7PB&b+dhM4fq{qOpZYU64X?F{;+TBp~oM?9o(c0aR?ObYi3(?x$P!XMK*9y_vwNMS+YB>rK'
    'TaHi}ooP7=(OQmh{hVq!3K3h5a2emqZ}G=TFnA-WHs6X-1zl-63bC4wQ1#kVdH8V|pCyC4iA_VIcr9CatSMY5B6`{ovQQYh)&3SD'
    'w!fh=#)r<039?Tw5gs}cKS!G2LcAt8RKGN@;R<H(dIv#B{H{&G;rnNEkgO0o(#I9z^>NK}zXaYAXg?U1VTcwmG?NSm83fuJEawzK'
    'A&2PIsK+IUqHvO4sFhN)7pPyfAtm4La06lRK9VOSe(tn!g=lSDxPo2XakzqQ4hp{`Y&3DWgV-Dte&>q8F3B2Vce_i|a=CxlEF^|a'
    '4!?hJk_v-|Xq$z?u*%#huY7t<HQOw&#PxHfB`!p3iNp1Cp(QRvYl*|PbEu^&#B1q7HFTw=E5vK*!u7k{8Q}d4vA5kduJ0V~y*3Ah'
    'pA&60AzE7vu3cNQc<!?~DEwS$4+-(wLs0$h=@HsP7}WPd5E4IE+G|3z_8L^bG;3;jcFtWW=7^r%L4qt>qbL`nWv{>}=#>iQ*)lC6'
    '5?cDh7%J__*`I}p<Ybmet3~=CIr`I}BplQ=IN#zBp&jOfD(6&-Lxk4ifQsl!i$jEVq7SB?6D<xA-ibcAb}qFzM0h9qU?LvdZ}r#5'
    'JGK;d=a15b#*k<6&J=c4?8N-eXYC*ciJmLnAQ9dHG^l<p13Hr5JXhKmBD6D8F!kCx{`z!lh~4eF7dZ4cWZ>7mkodW9+{e>)_cM*%'
    'n;QpCKkxTO;n$UM0_%LG3rB}OOK7u@7(O}%c#n?4?&iWC<+FCT%{@v~JBP+NMQCH3a0OlIaf{G;++;WoOJw>*_=`V9KI|HaIhbK^'
    'XCL`u@J1buzSM)Kh3dWD_stk-Xpiv*0Y`21zwo;<SSeUT>~H5re_({yABgIgCYOwZpUpwycery{=Ytp|daiV*MrhrsxPI68jm6aq'
    'IpEX0>}V9-=<$v4dVEp+T<P(R@Opev{oLvCjj(!rasAxs@r}@Wd~pRG>G6&5dVEp+junF%gNj7Xk?!aSuR9vm?^Lq5a8EQ(e#Q6O'
    '*SA|k>}_}cd9v#luMOHfo)*`xVo(;jJ<|Z!&Y_tG5#CG#TtkOu8bo+A4Nwisx8&>Nts(xzuAdhPKH<D9qaVqB@Mbgg;SeY|w9E{~'
    '9$OX!(>SUKj#&B8I0I*=jAQ5xlTyDpI>nWF5E0%y2wcCa;L(*(ZQet0{jLo5%eUu2pxU`I%OJv=Wq|8fw)MC3#|wv^K%0fc(1m#r'
    '5!yTmT)TVA;noW=i1cD6d?ZgU_2XKw@Pix_ey&V&iSVYmp!#(jDkZn4x!~G0$18^?KbwQZ&yi_35#BT$R6kdy;Y4`Ta8Uj32dEZe'
    ';AeA?__;C-CqkQsgX-tRVbc-XVbiE~?;V4d-ZjMDcJb|v-p)K*Ab#8IY>P%2=*5^&fKnJ5a0>J|Po6KJkHgndKlF1S>S>PraD*KX'
    'yB!kAIZ%rp#@YGlO9pNF5~`e2)0Yh1^d(G0SEer+wCPKjdQMDVGI-OMaP3^0zGU#GFJU4cPwCgUTSM$^R~$Py%-8?=eh`Gh@1=hE'
    '`gUuGz3m*CUS;s6SE1^;GQG;+O|QcAtJ@0B?qzV-g&-7u*K_f$D4@EJ!FvZ}At7{R446S11BR*R#27GxHwFyX?f{z{Zp_nop73xc'
    'F?3~=n!y{ThU#~FWpe|8EF^@kOjI*?6V)*Nx~8~tcm=UJDEyq6$z;%GGWkF@P5lxoBmH19LjeDC8fP^u!8Abw$1v(?iY6~KdVs$V'
    '$7m9s_U35_Mc_^D&tx)aGntU>+?dH^@Mbch`Z+RF$e_&>!qv-<4D9kFiJc?!gbemPA!J22<_Q_Rc|y2;9Sk+Fhfin*h8@j!(3P1?'
    '25%-4uHQATI9$Uv2ZdiA*GCTDKbwQZ&zYHE25Tl5uAe(I!3^3=FjT=)!Jv3(4Y9kO8&jDK+EgY~Jtw9z8MLWPsCG_FWin_}nQ-kY'
    '2ETaQQ<-q>9Gc2x@TM~18agzU$>2?8LN#<^Dw9E*%A`OgT6*0>!%Va+CNT4;rHphB=X8vbw=6?1%rZ_e*{avk7|wkFr<n_{4+E|J'
    '@Jmc(GI&#&aQ$4F%4E={GU57NS`IanEs5QgL8blnL@QJ~S0-8+yopx0ehy8vGI$fMa1C9UXl2kQTH)HcG11DPO|-(+i<$6|JoULU'
    '(aPXWv_kcBWuleAn`njX_m*;ada*f3{MrWty!Jt1*S_TpDx80Y*xSyDNpuEn5*@CcBa`S1-XuCyKUXG!8N5kgxPGoo0yAinz)=01'
    'm;`3fCV`>a#fKzw;M#@WuxA@PlC2Yaz21a@A5LZ(BEKKKWtxWG^Fx1-9$1Z@SfXGVMm6~+=!4L}29Z`_p!{V~UMO9kX!W$+=0q!8'
    'IhQ6{J#V-<(FzsOk%?AM^KDMFLe+C&qSe!M+Y_yj?HrnD^>;udxqMIU>Eq-;k;~J55QM_dmDxB?`)$w0LG^QFFv-(=o9`W{dR=q5'
    'b9i>PIVk*YMVvr|S}DxeH?&zO4C5qmp*#Bd_czEv;^)X@gTKQIa7W@-XB~_0ALJnMb7Q)}^M2dY4RHOMtYzT`IVk*+$B*vloWoC`'
    '%|c=5!i<Qg@wR6~;M!ffHxAdY%|YVl#&n41{kEq=;QF~U9pZVz?dcGn*Tej;Wej{@&I25T(hnLokCaf0R8mii>PPL*Mn^*=q~}K}'
    '?DZs!(prkeSDzccHymDrAqIt>BeM;jUqaoUZGh|N%4~z@1rrj#?#5yL{zhSUJRDd&z1SQSer`-Qcz*YT=DvHnW(@4E8HJq-Qz4$V'
    '+nx%6YUfaQ{?mk?bm!w5y3?Kiyy13tKB}Q39p=w({%&`eqxw10srt0vC!MOeehze5K99G(_ls)hM3?3BdiRz{FJ{6=^2_H)m*Det'
    'FWX&$$bL?A3H}}YHoF9I{T%2Ld>(JJOAy!Y?OL+9b|D9aUz;6RtT)>n8-4-&+b_YaMjd(ntd$u;=$H{+=r1A|WF%z>dq+|P!5H=`'
    '0LfXx<ggk3^w9gEcD_sXdA!XoRa83{x>TPpm)z`9#kF(e45Pn8wdv*=M!0_6{ldZza!~j=(&hWK-zQzZxPFdw`92T0S#6K%=R%k7'
    '({|fkzNmKZUHkRz))0H!xzOP&usVFlevzXL=g<t(B!h7ZRTz4Kn6$4Vn4`N$I8IP#9nAf*^zd>aj2U}>(Vq0?D9~T1!&jhn_@W{@'
    '(W5HRdQ_3^T<TF3Xg#W^hz=Y9@HE|-M9!J+RDsr=it1O#Hy36hKFw!yQ24ph-7B!Vdr|eie;fpZyT*44yGL0+pt>b-V21P4fHn(-'
    'VO*A(3wvzO`q>;LevWje3cSu#Tt7!TD+OL>C90oGos|Nwvl7+NiOx!a)>(;b=TK*x!0T+oHFTr1O`vtQq3XFZoK9d3r$b)6x^Y;u'
    'x>4A<(w8Oh`m#{{9O=svXnk4Ii$tg*6$HMLk-tpQqJU_c^gPY*;jHvB`Q9XE6UZR+Mbys#=&8Y5=5g@d@5>TseOah>MV(*ZsfESL'
    'fz3i<_?^L>W4pHv)vl_~aMJq=hYd@JLLul#XNN%R?7-HGnefFFey(&T2)xb&Tt7#u>jhqQJ*uB8)%60ex*pfhh3a~NR$Y&3=R|eA'
    'K&!6DwYx)7H%^^>p76d|DTHcxYrC(Hw}#l;&WQ?LfmWf5Y8M|WdOP{_{N`%IZV5(h#zikOnCHNZlQjM$hFQb^lw&`_3ZNfE5?1<P'
    'txx((6v{qQlN^*M;JhgD`3^^R{779`q<_{Af>8LmP#rF@s>5;R@)qiHeFl7aOXBBLb-hHZu17_5qPkw9Ro5fixl~;*(W>iF5uK?K'
    'muNNOsD7^0h)cX0aa2E7YQ!a0jX0{FBQ@d@sYV>t&XxLHiC3SC>*q*)uEeX)MfFQgIfoku#30dgsJdC=RX5|Vy|_@_EYYf)aqS$c'
    'ZkBk}&A5hcR5wes>Sk2EtZUym+<$Ejn&pEVhgE|cg`F$)%@VJ^SqK>1GDm$ddc9WuJlJEMCa7E%a++YsVJJL3&%Ws=t<}&E;W9vh'
    'b0ih`^-<)1h5BZRR^N=P=R$q6M5}K`wR5SyS>n|<qZ*#GHx_TcHV1`YdH?!$<()##mFiN7S6zzh=SX#_#H%hv^>d}VRN_^a;`+Hz'
    'T`JM4OHu8ds4kUg)up(04po;*yy{X^!&{c!INW<}4iY~Xs&ge;buOx1lDyH|sb{x2lFhXi-_vr|eW0Ro9(v>Z5gfTahQZ)_V>HV?'
    'n1Ws^SjU=YZ|X+@CA(sdLJ<xybhnpZqrz07RhZ)XwM`87j)MzT8c!2K779Zbs&o}rl`gKFQ&px4t;!S?F;A~fl)602XLFGFT^=sH'
    '^*+sad64M2P~)u7YMhbnT&i(aXf@8Lh|bhFE3_JCWWSb!T}xr-N`14!s&7WsbELjmA=Njd+Bs5Rs?h37arGRkFI9N;rMN2x*W&{W'
    'j~onb77{~;>P!`0ohh!N8+E1%t<Ds81tv?+92O634hlb4>U0%eoi6e#@QuTp@7A8%H2R?$<sd^)^Q87X<3(O?yjkd8!4wi54uJsN'
    'sMp@24ScTqp&w!X?gEDlMqi>%SK-y^qWU>eX{yjFO;PR6r}XRFts(ZdD~m4U@W^6wkoesh*xf1QsxCco_~zLh6n?H$m@2#qQ&c}!'
    'Dohn#g(<F|3l*jct-=)5&WQ?Bg;rsTYUf0CpF*qdL$!Ony?=eXHN@U_aeSq>)6b3|iMLL8iXtP#G{PA>QKS~%C~uj(In<-{dKr##'
    'nT+(|pMmQHhwqGf^!s6%X5ocV;D__)cDFYMcDFYQJ7=m&HCk0EvR_lf3B9>wLD<w3hAvc<YOJbKT)C`-w=}5CPz(ei3x#2RX`Oh}'
    ')lXMNwnTmp9()fHJr{~fHCj<AvYkssr5dfM6czE56i}7ne|<j)Lg9Djp?9XRbEcqKqZKrx`ngh+tFel5QS}@t%GF3kxu|w+9e;hf'
    'HN@_A-OEQTLI!@_3yI(T%)stWa>wl+-PgBUL+ovLb75QUS-acjwi>FPBTXC{t%<`62dSkP;FL8nm|jh085U*cFr0^Bn8RV5V30-_'
    '3E>H-CY9baEPlTXvyi%9^!#N;7ihfE1*nFu^p0!1-f>(%7s{74TKO`nofGA^8m;^m)vl;-Cl1%G%|YSkN(rvUE5XI}yECx6Q^>he'
    'f~)aLa8dm_4(}V=Wqi1H-GReb4`NX0y(U@1;ht-AQ204fM5@t>NKx&aC?eHpMWm>9@v(+tJ_mLq{b!3Ik6Zg`lkEL)fD>UnGtUx6'
    'lFoKL%BW?LA~eD?!k-2>@jj4|ANfLs(5pN2OCOEP6e_#w{uPQLeY9doR6m!>(R{peG*m-J%Bg&`aw=Rs7s{!8v~ntBJD19-e6(^Z'
    'RK%jJY7W=0%|YS!QonqCyfwt$c1}zx@bM-UVA_?3ixX#IJ<DfvQ204h%IBk%@}c@&&&9W*fEjb%*C&K5B!tcJ!r>COIY|5*sV4QY'
    's!37x9H}Ptk*Y~i?b`ZqhINC?g#nxX(?z9+GlgNC)Cq?d51WI+&yfl>AFV<Scjfd}#~kjxHV4VFfg@EeK3<gz?(5r~!K>S5l}0}='
    'fe?Cz@gtMB!0=J1)s3`<iKIg?P9aPx9TpJ+tbilh<S>N&JoaiF1`(Ob|6K0U6)awSZ4L@QC#p1jyebV;J2$E{e7q_ROg&esG<?J='
    '4NSjV-F<z$HN@_AEeE@n#Lk&2jR37mqo1Z;3q4ML0MBx>?}ZBtN{91eCmjSsWR@T>aFDDAlhKyI^9`IEt8KZ9Qj-@AN`H+ijR37m'
    '1J|#+Iq|OcG#})k@N;2YRe&|F3Rljd`k(->J_y(Fez^YQ|MR08&@fPhG!%-CR9OXRRaU5a$7}ud?bZ-`+g0`XTmA9k!YR<t3PKbT'
    'L03u*0<=;CR6ketc>}C{UQ|6t_IU%OeO^>MSN13aygf?XXTSLEBas1vS2sukpW1(=xPinShi@UoAkk}JtCs^`Q<E$oxU%6E;BB~}'
    '`Z=-T7NBjoq1w5!Wfb6T8R0&_xUzH~qAlG=8V)!WW){HbiP4{;0L*;f>&Iy7{V5!SS(;GJ0n}~GzHhXFkzq5aDu0@_|M}8$+&J<5'
    'dzR1UAn|i$>m$TFtpnB1k*$vqZ|eiq&!q+Y5b?YTOhZ?eUqZB@&6s+QEWd<ULz^+}Tq?5<@yhH`4V`%V2+`g?Q0-h<{tNMz|8SpP'
    'n)`u+pUpw?^m4cyIr!Ne6n>6unumBNJz?s(vThpUt()Tdxw7pW;vE))>F3J2bBMR@jOypg+G&Wlc8cofM7e#4R&I}L*Kn|FNbH<h'
    'vyaf$?EOH^M!=yR{-QlO!ajz9rpW;?6*MJ8<EY`YAXM7(<+7My^aeFgVpg*!XXOuHW6e22TXRPBb7{>q!do*%HFRXvFG5=NL$z~h'
    ')i1(Z^+PpuV%0A~TlGV=yK%6)(b&1NVjAJCnBw|fuPpekSCS_`N2)a<ylM?xKS!z!BD`t?+$ZO_J#n~vZ4MGYNA^1+y!{STzss@y'
    '`gj+bRRdR6n<Ko{W>mjx2~inbyEX^OTW^&X9Q<q!lD9S&R_i0Q)p}gJhJ#(x{U5#BY|vJlwWoa1&p~87ZK80N(d18y>;pJ^Th2x='
    '5=II2p-_SLrLSPPkcLi$-kuu;woCM7R+|mpYBQ>#D`x>1yt4ps{Z5ask9TTX_;8J~x1b~Y9R_K?1J%x@{SJe--+^lA#D0fC+wZ`&'
    'Ybqz!?4Ra?93*~^jsf1Iqp)*jzsTV27vcK3v0r4+_KQ&U(o0cu;IlbM-rXG8?=X1#9jJbJ*?fJxHN@U_r_1HQ;k##ZQ205qS7gxk'
    'ig4{5*()-5dqt>zuIv>VyuBh+zvhs-F-`YbKnOze)Er;Q?O>kjlh4fY)-yB6h0_v2bHbpE=M83FG#pYCz}ZCsOc{b{Lkmn98ug%k'
    'Bc<{Ed7MWNXno-+t<~ptw>JiMw>JvA^ia1B{O&!?XLFGFIkMOGJmBVD8>*i}du>k>ezMnwYj}O<a0x>U3cXWOe3a7v`hF0E!mlW+'
    'n#0%6=AiI<sb9W6-Wp<WyEBg~_e^2uLWRNezj?o?FhCW&o{Miq@o^O1*N22G6ohURX*{j>ox-lUb#D$V`8|zib5QuTKWFfKZM=4K'
    'kPxz+GX+9_2f_o%4Y<8CxOmqPd)svf21|Zxh~4cRC`^0aZnH2A)$W*`QVuV>Hpl<b%cTNsxir)hj98Lk2x_n;q+se&?*+pcz#+&{'
    'G)034bY_{gP!jg5`e<C1FjD?91d$i|{g+uT6?n^~sD{Vv_Vw}B5PRD>^1ddJ-q%p=TzX~}c+bqJhE6=Y2()Jx<lj9vo?QgqvkR)<'
    '`SzN9tBd60EE!zEHVw(I;HA8|uxj=6FCgTg@Vk}Wg@d2XLE-1j8;C@E1Cdi74U6de&=X=%o*K-cLpY=@n3U+3VIJVHHYi{7#&DkD'
    '?;;rlY7{C0)_#)Xmw5w`cyA!6hK@W%OQff0RJ-=2`ucKfh~4cRdIOPoZy>0KPP~Cgv^Nk`ySVBq7oJ_7<+C{`{G3?1l4vVesCLD%'
    'gS)Q(_5C0Sg<oB^^|$lKi)8TVY_pKue;s-Em3Z&IsD7@z`%1ibUsOM5-hCC?yYHxl)FzC4Z|sM_44#40$>#|UKJooYnYov6mU$q?'
    'IT~ai!AEME`$c%Y3g=!&UuXAC;l2B!8s>*b?!q<vte?$6;di<?aRlDeel`b%pCfB83Tf>H)y}2$1BJJKfNJQ(`hh}QKR~r}W&J?m'
    'tskKJIr9#z(B6Sj{aktnR(S8gxc87t*>ZS(u{kLGoOy@Sct;6Jp?f37(GPtYPQI_A0VZGfMjGw=(J~u<2}~cr0Bv7O9SxKAf-wxD'
    '9?rmACi!LF;WXk=f|!Pm40nFo?~~!qxPC6QUTWmlOH@He-r_XYVV0P7F1^KR#KSBx4V`$4(|CtjqT0DJ-1&LF?cvU-ey*&bYP=Ox'
    'R6kc%P&M8PDypALZ^0VxEg1J6?8sZN#(N7!^>gMe*hhN{4yHK>dIKXSy=9!HVS&+;Fi=u^gSPv<gQpfV`ST(pqXQ4BrG=TbAB;LO'
    'aGKPze3`dkAMY&~)iBSRqYL-pXZ>sr3cs@(kActfoj0EXQS}^o1NM>LfKlz7nEc|SO@2YPb7%Fy$6GzXHM}#pZER0|LA7&Y<;6!^'
    'dBL@F;8>{V?KY2vLbbca<@Niw>-pm#8QgZW_C|pi$4UI-wd2nY3Ml?M{>wklKf?So{I~l5EB@&p_!G$g&!78+r58Ls^*-6U6H9ws'
    'KoAYV92h9ro%~QOQp}TzJiQoy5JvV>AQsO|i;{~li|Nf0+IQpt>VL&A4k|0Y)gNas;$*ow!x)+Jod3AEvp;<y{<@kFi^MZ+KaxKk'
    'i~40L)0PA>>$XSCep$<`BeBd&PKbF)f><0mAr?m(#CKMR?<9yNtIN5hxt!~q6JniHAZF!_6(SU;|NdX0_O?vo^jpnH6Y`KSCdu26'
    '7n&Ez>4nC|qT%dVDUv*YC-oaA#4~)hM%rDnNh?@JOa62Z=F5UYC<@G!ks-;wCQY)B@=t4VzAR&s(LkPHLHEFFK^HQSQ0DL$`Ele$'
    'nbTa}r{?~rbvj?x5dv*M8ejHHI0`cet;ZRTI8aj*C@CZ~>Wvci#D;Mh#y*-RZQ#rUB}YBYo*ZEe3w->Gn#F<>VnIV#=e)j)#paR)'
    'GGurB@qSo(h7~8oBJr%^k3@2M9EU_SkQuKFyvj%zFPzqO*EG8$c1;Y8E*Y=u`f{{?5~9(3FK-|5pH3k8x}G-@$m_j<C7@DhPL>dg'
    '=0a~zyzV*>hywC(V1)QH%<hDF3wIn&zmSlK1hQy3Ar>Tv*%eA6IW6sGR|>}b#A#1^O|v^<(ItP{Z~0{%ArJ{<m8P)v!$}enkx156'
    '%uKSTS@+4C2UIz8dYOSl6p%+wkKo6xNAMu*g&w2cXxWFdA3ZgX5<C~F2jvfPQA&kM4RB8N6fUFib>uB-iJ-GdMN0d>IA(<tVMan&'
    '-#Ho9cM`<-$_eq>k|4IM>Pe3zh^Hj3SuK#+KqQc9Vy7pZSuKIvP$Zbek=3<*+U!QcWqhqTA-+}=h(*fjp>a*KJ7NnHwK&~oY#<8A'
    'muto9ml5(%FrG6`9Sduky%9NeX_h2_*{S+btCzCciTM$W#Ixem%(bT39kJ%rH?yYM9r5y!vw9OOFBFVb!l|;p+8lv|i<oixRje|S'
    'U&YFf>JgkAx4w%?O{0*$GQ${7-aHsRX)y;fgc)%#>f4L_MfIMqhrl1;*y0FUkKkD2DKbWnCRjc{<Em<)9*@(mYE`B1p^Zhtc_|-1'
    'YDGDX0<fWIFl)GJN30}k63901SS|M0KqQbqtBANLZq`I0BOX~H9!U`Ici7tE)GY&vC?M-J{fJq0X4abpdbp66n?2{`!0Msgh9bf2'
    ';w!5=whcrB*|f|co0bCd8oxbQLE1nhkU6i7SI9%ccx*T!9vc$G6Q_EVHO=mbtoCQFHObTCwRz=)_%qGkh~LX&3Xk9?R_}#26a{9('
    'X{<++QxLXs4x`};R-@q{(*`B%U<EUvg`)}vZ|Y6tM{vGR?@cC@S_t^WcuNl_`t%|U{b2}3v&i1>=fzj!uTHT|UU@x!+dw3c>FLgD'
    '!^;LDfh^*ZU46X`MS@vYysqxDB4NDT;D*C%Ik(-MdW1{a6|jxX3bHF`AUjrw9SPzar}FSM&EAOJfzv|8nr3&zGEUf4_}EY+nAMrz'
    'nR^h5#PZ5%L3~ZKJ7UA>e5p0f?uZXgPdwX)V51_w)+a`YYnuHLD^`dkFV(Ltr=rI-&EAOjxO!#SS@<IsiD$xYq32HX#Y|$mWyop_'
    'E@axE)Qg&<rH{NG4&(7h0ji4#v=OseR3L_N473P_F_`*ENMlF9Ei#xQAr=@Cr}XEPIj8sQ`{o%)sECj9qhQtZ@hB-6-xE%ckMEmD'
    'o8clB7hbctY#<8A_{vFfO|w5@cVo44Z3B@&-dQQ$&lHHsgVTYy4+_FGxn!&^Xd8$G^1$ra%)_08F|T2Hg4KypImzQr3cV$~E^G({'
    'pXOyp!I`C}3#;qf2C|>VU5n-U`)^wGVw&L(1#0v>n6RRCKfu3H&<FDzh2c03(=sdHz>3l!CNBu4QHo)i)H3&d7=8Z#CH0lpF<v$h'
    '$#?r2SFC<2Y#<8AysLT5xUhjJAdhvEvie5aKopRtG-fq<oMcVCNX`wfImHl&1oHOIN%3czKSRWP>^UEJO=W;Q6pZC-`O3=C2BLth'
    'UhIUlkkb^Pmzo6f%4zF%O|v^<n-;ugNkSkB$T}@~4dt|fC?Kz_##>Y*gqOpC*Swm`=4s=okZoN+p;gMNwgoa#P<GAn%If#g1|orM'
    '%b3;0Z39t2zLp&?NE?U(l2iN5jRdf1&#b<QHV_5m{rdQbC8uGgkca~E@y6*~sx{5th;dRt!^7FBQA**nm1~>FuT0Yr2_0x1dUEdV'
    '5UK!HxaV1gk*8qY+t;4%Vewmg((mOU)ExNz(5p#KD)iyM*r$|f`;j=+ar`u7+LAzKoqOHePg`ytXM<~*mz)suk_53hazflZqZk?S'
    'ofYCc31Z3WaxQ5u=Q`(vSmzXoS$SiH*j4c98ftILBu<?=>-kwt$V0-IByT@@;a{ZUqzSQTI6GE~B+uVT{l*FL44<u$c9(2Ym}LrY'
    '*a0U{2t|RJGBPB&*Q7}Xv-%__#v~(wJT-1L**)zDfk+?=PKX5!VV(2(E*3N|hiTCre>{noPEAsJo)cn`cvkU8A~`+yK%y<k$Pd-*'
    'FESi_t-Z+?p}&kO?6rvi8UC{uKNR8Ys~P$fW-o{)VJ1EMlk)WFiC;iwye{x6BVoL7T0vXW?2gzq@wf9w#_PJi9POWkXe6Z9d-G$6'
    'w&p|%p=iFJ?TOcqB?O{?{8<;w1aY&-8J93`;fK=a<e0Z4kVVT0u^>Urt{)kzwV&)t!uYrzoGQ0}nh^p~K<07VvAR>+KqQbSPTR0+'
    'n%xnLE@5?9+dw3cRhq&g8Yf9eL?T&NF*C`UW&tg49#ELe>Gc{CkwA8w_G|LZGZ0Y`j~OGwBgs<kvA%OMtnVa<@s$(eb?dD<=%wlh'
    '9eAM*0`0-Z*4$6w9EO26!zu1l*b9G%=16*Co^><?avEnHPM~gvXqi4oY*`gS9!U^SNnEpf6|{j!Ak*aR+%e=&V?rnr%;L!E+CFWz'
    '(BLw@R-6!DD+<IS<@C_Frr8~_ZH}yNGd2(f<V$^Rpa|f|YH!PiqQQh+LZ`+SJ}*h~6!~(kSlzE*t|YgbbKGV2;%4=gw4q2aGftf}'
    'Ynr_gIdu=0B!Jnea`3#}r!8$P63>cLli`|Xcf^`gKi8UOZ^SBQWVpFGh)bAo+S95w$4KEKW}JQztBm9qvC1>JLkmuj`R4XuuqXv|'
    'k?uVorot)V%|ZsM52DbUhtPzJ5dCPzNWe#96v247KuS0OB#ew7sLvto94=Ol1qox*o><jHRaFWf+E^r<m-6wW&x6yP4;zXG(;oH_'
    'v68GwAlsZ*8LkaP0{OGvl8fSY^(Zdlkrm>R1o3`{5&%vOnvjSBvQE>FnAI?Vdb^Yv74mW`;nC;7>Y?0*BEjsMmen2G2BLt3bG#p{'
    'AZ;KL$RzFT<t;hwF4#~cm^rT^705%vcx*T!9vc$G6Q|m}HO=mbtTwu?HOUj?wRz=)*t}98elL$H+^0{h-VJRi3e1MnG^u85n3VF2'
    'TqZcn#~-7?n_<t(sM!oNv>@57FX;_K=)o~R1Hi&D?aO3DZ_n}3v!16we%^u9#yOnhQ?NS62QraRrl&iry&4;c1hR-rb}ckE6bWWo'
    'v3i$*JS2<`o|YS;otBGBdAY$Yhu5MmWFn#L3fRnM1=-PjC%cXnVn>4b#;MYNO|v&*ci^;Cv8LG_v5XUTbv`x}31)TXcdRCaBC))3'
    'S`zOz+cj|!8%{^at!ef~e63H65Z5&OBUY>sNnWjATTWGbYnr_g?{W3Yu)pv}EE3Oz-5SN6=8KuccE5|&oC?UaK`DYo2eXoL@&aMt'
    'e4bejqtx0=Q6K3A{xwk1;+t8kUTYy|HK-{F;AkIcQPSh*%}Mv1)2rc{W^cqt`BAW1#eI|%jPD7j$Hz6z?uf;O*U&v1hypS`bTGh&'
    'Q%MCRB7wYe`Z}&@_DAe)tO@~aAPUGdxn!&$Z6FfJ1GBSo4|fvAyoUE{PH!@hhy)VaBzRre5C}fa%Z`S#DVT9K1qEbQUwIu}XakWz'
    'UgL__5nT|70y0m&-Qm@S)xjwV31n9@JL?Prkw7*nERAPUu{z6#WG(W@Y4`9*^80wK;p=#2brKEDckz7YRGG4-`LpqH;SzWz82sL!'
    'rcnA}KTl&cswf=B$m@*}+85)X#y;$$8SFf1R3wd2CJg;SevVji8f19hoOy<ec!A*x+#Y&tC=$%Z&X$7WJx;3@HWUSB`NpYIWlgg;'
    'B24y-c}+WmKqQbacK#lxBLW~12_y_F<#jH5MRVt_uAB-~)-<~#K8or`#T2XQxe$s1vrbE1^K)$=63DWx;YgYnR`aE7C=$%eoz)P&'
    'I|<_BTJV~|2Z1OcuW@~6HiNGw`9^ll@yhCEV*`;uwk5AuL>q_#^47FxR**Ij1>`+Fe#DYf11uyWfxJEdlGCdVB%*+f<7?^Er5!z6'
    'WD0>cAm`B6{S-ucQh|<)TKvHmQZ9q(`@xreq@X2f9E6^Qn0wF;VP{OqanQb=MD%%sQk=FQiBrApPfMmP3FN`Co6XaXhs~P}E@alZ'
    'H*n!;%*_M6a4qwa6Jk#D6ImQNAr?m(#CKMR?<9yNtIN40xtz1|#tE_RD)@8_wYOywr%s)C|EwnDAz@6Cw;$sxUYx2ceOeP@(QtOG'
    '6iFT(llqMl;u$_$BkeBPq;^X?ajHZ6X;277ftfNgB)Qk5Nd}W4B`3xtBZ15s7+>*`OIDT;iUjl2+*z%j*+3+a1t-LUhOo|geHS4R'
    '4P<xx@mf<lHA(JyPKdSP8ICg4^D-^ad=!N9tj(-oFAD_aID2YXCU1}mM$82=7{*|LT`({7)fD;t&@XnD{b!z4{E<jbPmz#_1~TJy'
    'fmay`<0a>Wc*#i+yC#Ox(u~)2eL31c3DHPMulMH1{Cmxb6hhH_Kid<pA4>>C0eLtuLi`zKcf!1dA4;E-W8P9gW<RGAbGqeZB)6LE'
    '>R9jG(~MUN#yoC2RyP?Nhy?P)X*+gJvpZtZB~EoRJnaa9NFbXB)bVk83Wr1_kR7LG-F)+uLsZ0L#>ntUvf^{B@0<)b8|82jFP9^)'
    '=7k@LNGRhgC&nwu%iytPRl|4OM4Tso5{oy_QQ!^Z7zw#(HIKunm4d^6d=;6nHzVwUNq-g*?21V#A~*mD8ksz;K1Dnwan0(Qwt+|>'
    '(**ixKF)&EGLH>Kf>|6{UE8P4<^^2F*NPM3Yej)rq@13=*EG8$w#|{%ZN>(ofPAU14Q#s}S?wm+P&AmZFXPlKzUL)Lo+4ka6|4I-'
    '<e^}MiZfQ%HOaH%Ipfp-vZmP^kyF2BNdj1L>g8I~?2cG-YMWWp?2Y)dRF#S0cHJ#5VZ-X>1@e$ECY*Ky*EG8$W}I#;RYr1Ssqzet'
    'gcO`0bCPwP$__kY<+ycG8_=4D(VN0BRKAh3@r@qD92kEY0xf-ifgP^V%!8WyMGoOKjYBj?QxAV?>AlYxoA$)2a;K_N_|V28;k=ZO'
    'ABFUsrc&5YG?@0liinkDO#<2GyoyC_AQH$f;iR}(<A{rRzr$uVr%HNAL;+b}Zcr8VabWcrWJ8f)c5sRur{72$hyoH$Hh-{!w1G$<'
    'lhhu?cVIOx#fBom%z0G-KpqmtW5WsY*pMKeI2A{&X?90swL^2=+@ZlmY+gAb{!Fts;`j2H+U8(ZuQWCk1!lu(KuVKS5Vq;*&T2{5'
    '1|oqh;*woqy$wZzSyrqbz#-4pggDPzl!-KKY%Pm{iEz+!<f|bP(08;<qwh}!+K!@GPklJd!iYWqa5(u#`AUf~{G74oR8+C1*&h*3'
    'f`o0@h!tf)LfI9t+r?>EVcQWwzI?>2D#9TV4P?g(u_HmevwDEMpJ@=^;F4zb@OXctfb0&O)_T@7yCary!mc#Mh9beN&isztgHR-v'
    'S5A8h-DX1}E@H#!jIK4!?uZXgkB)1ay%AsQ6C=bm&HjiLD@2mDvezczHDSgEB7tl<l|8O$_C~zroL*wqG<zf7Ss~tO5Fh17!D{XM'
    'v9+Vs2jj39GY7$F;DjEj2QOL{342@9sF%qE%G2{8BPHRy9@(pD?8B&+S}nr&NBQ}V)_cO~L1#^~J7RI+b&s}zC?MlQ2NPvDm7qW('
    '63DX5Sd~xMKqQb?PS^FCW`D%)#_QV%fhZu;<ihK+wt+|>56sRTJ={qc^BO8pIBgC>A`-|;_r~kOhCn2c(CEYq5(2@edD+o$HU%@z'
    'rl5e#>MO7F^lTs!$ZK4&`bOG76p(pbADJD#RUb(plW%uewP1DLQ9=UQ)y$5AgFqyZP5P~dBQq7NBe+ru$|I*O>?6sI=2*km@yzM~'
    'sm<@=2z^FgAE~ilJgpbi57THO31{~7gBN(?<cVI0a0({-SJ5(sz$dioWweNKo_=wxN5Se)kAeiT<aLiZZN3<yG8W%CmFlf&_C`FP'
    'ITekrX?91fIQ=S~E0SNu^92S+aeIrgp-3<rJE;)r>RBB|(c~mIn(~cP+1{FFZ$y|A9rK!<34ur;VPbP8B&$)wBsZMu%Bco&O|v&*'
    'otC`jUfVz<kY!uLv2ZV}rWD#xB$$^wt5L3Z62v>RL9X|fh%x5oNb=xQKduEYNC-p$d5!Bkv&q6W$uH!!eQ;829~6jPbG)*8g0z7)'
    'AoaM+!7xW=P>~7;vp}zr5Gw3L5%yyg_FfPgFBmj*AVC)rC<A3UhNAc3?}PDk$hPElqp^V~Aa6~3W(8>jQ9#}gPzlKi(gq@dygoi+'
    '$?13sNJIhoc;j>~?wV$A#P_b{)M(hX6o_$rEuH#pG|x69L7)xD!5gI?>ZKpGR&rV<-x~(uO#=Sf3#1l-7b+v+pQyz^o3@?;Uxm@='
    '!;IXiUxHsWY&v$gej4(ydAG)e%sTgGaXpQ>c|0kuWnOYZ%xSLd;>ZcHIMN`#vqF3)K`dEa&Lzp^oRv3Dh;>)Nr)#L)zmT^#PL{Vf'
    '3dAIa9tB2>kcWgZN#4GHyV|{L#Yq!l(QtOG6iJ@HlbX}-V{(Si)=0ZcHYpr9^N~0;66tAB2t|RJGBPB&*Q7}Xlh-9D#v~(wJT-S#'
    't7bM331q<uv7jNWb6(#?2t)!|#UF{}bfbnuG>{puFJ!fKlkp~R3`Flu{-nJ?s6fDfn%4{8lL`ua6r5CObR_#J65-<e3I^xONqSn0'
    'Dx9Z4{bHn4&I$37lOT3Y429ttuj~49w0{z!k&s^R&5t8|G$&FBMf3e^PrQCCArJ-R;lK#-XPDgy^A>(6eNK*fO9EN6oDd5V#4NVQ'
    '*|WNDXC(LQ?CMy@>(h)^3dTHcJ63mU8;ArlFK)abArJ}ViPQe;nr3&zqD!1=pn2L60+B#A52$|R^iBwgNFX~-i{km_LH4MK$BdET'
    'k!1bxc;d9-x~AD3vA%Oc-0T!aMLZ>O&FYEK1|oq>6X^E%I15gTJT}w@<}#1MGrls*81@>DF6{fcUyLu{NJBHtgQp@-E7;WXhe$^X'
    'hU89C&C2g5W!taCFQ&O3SrtH@HcRYr8DA?-h_4j|Vv%xs-dWS^j@ULwR<{`&hywDZeqp4zrr946c4I`y3bG}EyjHC4(~yUP@tkog'
    '3SZOgjmW7Ht|S30OIT$zoES?Q$cj^=%$jC*#G2C**_vi=#Ggf~Obj<GZgB}SP8V~PkzCAGp21nTf)iv;@*Z8;F(|AY3lherJ+a!E'
    'uBsG1w6RDyFXiJ$*)pd#Ya5CNv;N3M#7eRzf$S1ah?}J+DwvFtQPeB1mof^4RAc0+Fz9tJW*uk=s@jhRwe-?kmKjbnR7#t00pMl)'
    '1>*e<ds>_-MIjLdWPQ28SiO$}tGl-iMS|HiEvxMW8;An(8oxbQLE1nhkV$IKH9JU7)!;T131-e~vk>x-FdiFDh{uKm@m%m5J_?~o'
    'ELpATUN_ftaS@wWPKZC#?2Y)nJf^k>j@6ru4Ml<3a2lr2<P?N$db+b(khFnFAd9$USB7gtkzke;tLJdYL&8{d+J;@z?2mY`_4OI6'
    'JGKo)g9!%~!j5dj%97-rrtJ#Y_~KMG)pkUX9V^7Gm9svGMm^7cs9_@9;QI@-A88rR;{qQn##7!n`g5TDvG;`O<uvxDHzBkv*-bFD'
    'e16nk87J&^Vr?iA%<9Z<=?6lQSYA1;MXqUfM{GD9RI#Sn9kFdc3RX94NJIhoTAvspu4(p1tXLsdB#2GItBKtPB7tl<l}xQ^_C~zt'
    'oOZd^G<zdHO1MdLTAp~66pZf)r+f68W_QHm!t3^815rT6NpfSg%Vh(RKpr|~E8&oc1hOnMUf)OvL;`tbb<*|EH2WiV%zhss5Cvp<'
    'V0MPo;ZDMM>E2j<A8nuw$k8m`*pKrxM#79*>M$DQ&@ap4MR0IWIL`JD_;S%f0OC_W_Di^o9&CC|6YP5Z;#`lI86*UPPxG>);cN<K'
    'oJ~Oj*_9m};ZsUh=go99-^#4M@;YzE1|osH#ucl}+XkY5%;WmV>|BNVNCKIByTc1Ns|oB031kB&+rvpniq$Opl!Ee96s#uXk~{#N'
    'N?r%goM;|>;8@uUJVz$1x?gQ563p+Ms(jWodn3XS%9hnLqzyy@dFE8Ox2D-0vEp>EK3637>hlGLesFsXx1mTdo7~Q;II`-Kv!N(3'
    '%QsGCQ)`;N5n(iC%<5U(1|orkA(6aJC9O7ZIH4y+WJJ{avk}2K!Vozrec13Cr!kDAHY(6MFlwB&@goB}V|@<?08Mbf&lJif_{Ai?'
    'memx#mIU$2sTy)kvo~U$mb~Vb+CU_bWn05S#S5#23LA<9^Kxf3%kWNucxN`r@ZJ(J#@rlZ63EB3-~|bRC?KzKeP=dWv%b?nzNM@l'
    'erzBT$o9cWv3*b=wr`xKovms1M(mp7mDMF}1JOVhS5`L}8;An(et-&HPLMVb3FP(h5lc=(?jaEc<l~LgiH2*My%FC#PD{9Jn!OR@'
    '_*%O3+X(ZRo@`5kKpT)k1cP1z=}rD1Ww2;7FN;#c5&~;)#Mna@&FByCfBhvgQy_ggE<JSKsKA4RY<|(U*`9epLLd^ztaENM*YlX0'
    'XY=7&<|QY@oaV|dj+_vSBMss^E5vsa#FEwJT#{VQS$X4xSa%hCx`x`@GKrz(gOMiWAz@6Cx9{JscJEqo(u7zvoE<Agl1Im+e&d9A'
    'hR@bWyGu4H9JTO~xHQw}c~A&NftfNgB)Qk5Nd_atB`3xtBZ16oIAy`-1ew<)kf-L(YURuZB7rP8Ar>@*b<XR%2!Ti-s~B2_IX&?}'
    'A{xky*B7$dx?4-XH}ec9&cJS(x6DC5!-iKhj5<(aSOOD;y_$P%rg2oB2}Kn6Mi0W5!=NM28-FqGEa!xH$w?5qCWZ?8jMsI2Iodx7'
    '(P&896R+zV0#QI74vY|ghS{AkZ{gbJ^hN`TNFa-r6JkMvm|flKbbZ<}yHYUbaoe%F!Pr0~ka=<A1qp#jAWxjO4A(TfBNkoaQkDJl'
    'ju40hvUxzQndT(fJV+orPRoz^=0Ulrh{ueP;gMve=UCr48E*Dvq9UG>xMuaRV*`;urine;{>*Bl(1s$xERL+o%}$%OxVVh36(_{k'
    'iUP4nIo+z)G=G9<h9D493vZZo7{Vr2V1jwkp)%Tsexpe)qMy_lPJ<p6F^?XMHIuzGQ{*ikAb*b7Hb+*s85@WK@}-8QTM;snghV8e'
    '*NW9G2J%oa!bD?6h-;d?5jiz`lq7&<32Qrs6JtpOS#heUU(@W4SaT{~UeoN2__GL$iQ#5N87^VQ>0+)jl8d>r9qNLUV?n~$v?o^E'
    'SXGt6hc*@o=cRnWYGWxlwGrA-G??{AE+STvH3?*wa6;VNr^ZFR-(eSlQ{gQnqJXTsre(F}Xai9|!l=^+D@YrN1TsnOc|8ZosoK$o'
    'BEigg?I=K=4Mq*;$@t?OPHLXun3+iip@AK)VV;B%LdhWt`e_)Ar$%E!H4kD5m7Eq61yS$K(dUfEh7;nkAwgud;&a_x@xeuGUO6HD'
    'OtUv)!>RkN$teii^mJ#nRAB>=Ko)Vyt|ZEaBEc*xR*yT7hlH_)gHd3d2dC8@$V5Wf6|exwY16gsh#)&wh#duDci{90zNXn7vB*AR'
    'R(lGNhy=2X6L$MEHWUeFb>=rH972&;UO6rItZ8;fbnL*M=N-2X>_LXS+?hdM?lh1$R*E+Y#Mk=72ysobKVroSach+#42>A(V3N>R'
    'B*Z-Xk&XfxM#`7H=tIx*CvA7RR1lb{H+qcZ(nIf&>{UO3=jVt`!mBIO1|orMIaQ>rY4%3E=bT=x*ED-0KFW`R)vDv8q+oncINhVy'
    'G`k}f7hbm)8;AljPLdm|twI}!1oF^9TWi4TRK1P_vMe)R-$)2V0$IcHgsdRzjOH78?U?;WLLd^zCTn>?LLdsr<Wa(<4J{w6&gp?r'
    '6qxCydt>#jw1G$<uT8-V5(1Gxc0VrfQfgMy)`>3f_lDQh`uB!{F^}sbv*FD3kpwdNc851bR%2XA7IpLP#%hY|)+2d8c+sdwEuhUP'
    'T>Nl>zM?^EA);Oe<21~A=%YYSQ#fci-DecNP;+3k2xc{TL;v{*(!+t*!;cL_0eLEU&8|Of-mP&NubgHTu4(p0goD&B@cfvt>e95K'
    'NHD*1y3MR<_C|!Ubi7u6Y#<WI3ycKd_WWo=kzh8t?Pfo+YVWe4C@^8VRm|!M$Oa;Ttk2)-j~B_QRva=>P}XV5Yi5@XL;`u?bW%mV'
    'S>lX~cxN`v=iU-A#@rl9ZZy}pzB8MORNrYJ-%?h$85@WMvVCw;Y#$_uZ`YF7WetHSAlvM~Ys<?9B7uD4G}C8I^CyVD34(Bp0B)H='
    'VIl#4=?!6IW)Pef<r_G$Cs1QF8rd&i6v;7wuB2dzw1gpY%jXSpcL;li_d-sKx;7LA<}J&3mGs#_6p;5r{Ko1x(gq@dygoi+$!SbG'
    'B%*+Pym2~=W=*p<;(OO}YOd*83dA^0V4>pU#i<EX;@OgC2(^JZj^m_9Z;-}J)3Ef>6v$vwfsyc3Y0M&{xt~J#n^A|+6b+G(qwxAg'
    '4C6E^IsO9EvA3G%AvfP@a3Njm_!4*>U$~Hm_RQ-W34ur;p-;)V=}1pwZuTnSTIMAu#GK|Q^5<d4To5;pZbn9YXNCAqf>^S;oJ*3+'
    'IV*3R5bLgjPuEa;TPAVp)S<)AYC;|o#w2<B{_Sd)a}_5|h(*KMu~H;?bWF|-tJj(2bj;vWh()4Vzj3lWTgjT{;%-tnIN&33s@eT%'
    'PzXhVnKCjYxpSv+^>JYJRfI$&kVyv9#U&@mBqM>$Yd8+X=LDJ8B#@`(&gu!s2HJp(2I#R?{tT2_^=6oaKg^-_0`2u??tLH5GV~_x'
    'i(dBqH1}#5hCql>fw~E%&nM`n1t-LUhOo|geHS4R31k&RBP^@?brsV<rjFI!KM$F<M3fmb$c%*Xl5;}5(EL7jO$=qF8Lywn%hCQx'
    'h(<%&o_Jl~5Qqly(b@tk$?7c;LQ!BI4vY|ghS{AkZ{dfM)0;LVB7rPgPKX5!V%hQ9u(5$CAoIBGSV7uAB#?P=;{^$UNFYy~YAn_?'
    'yCW7|!m7~O1|orM9#EXCIY~AT63C9z!g$`1tc)KsMux|&g|i>qTF_@Sh;TB-6OkHaD0DPy-}Fl)LNSVY2%@Q<VPdY(#tVXIQ6Y3>'
    '!@p|tIbnV0WVku>0~PU<#5Jpj9UF)QGEJb5=Htw23)_Yw!7Prf>T^$<%?r4UuN5c6*NOtMNIBiA*EG8$w#|{%ZN>(ofPA@DtbQ3G'
    '4+SF(K4yftrr8^jQ&U$-0$7%?B*AH}LRr#4)|@KB*ED-0{w&C1Vz^mdhD(@n>fow2oBweUoA$(N#k;Cf_|V28;jEeM3)(;=keBiS'
    'D?Fv()az<P(O}ka@N2|Ml4RYn`nj9N1#xq45EZd*IXyqFY5oLJ2D2Z|^8!a02L2#@qvSH`VDfx3nQ;zOAB5f_=cymHp2Bf3;iRA|'
    'X%KS+n_JW8h+WgNy3yD`6p%2t{J{#+1|oq>QhPGefmP+L4Ml>P^IE}$JS2?Ah7;nkAwgud-gB)<?$_7ml@sF6G<zd{hcOC*5#x6X'
    '#D-G`T$7U!o;qe*36O{avQ1BSR;!OT5D8=vm+T6nY$y`UvSRh{4S7fy>jJ)#DXVoy$V5Wf6|fY}>4wvGM35aTM3TF9ci{9wxTe`1'
    'vB*ARR=Zn}hy=1a^E(OvLXlWrIjxtiY5oM!Tb4nFS}tHFm!S_ArN>$KqqnGKoXiCKSpp99G2=LkAT)56Aq<flbU5@2?0bE_ztuGt'
    'UNhlrAR5RUE5#cH;%j|kgt(^JAF*PESdkz$39s%q8;At5<y3{Trr8_uo^yJMS<~!|_$WULR_i;Dl7jKQxbXUAw1Frf;k2NP*Fl94'
    'hy=2R1NK-!)|>V9xR6cO@`8jw6p+cIgl{C2F|#_-142<?rumW8?EfPPV)x@4SxU`n)F{z6@}1XULdZkGn0Gf;<Dy8G%#Me{8>@S^'
    '4MYKXDtR@-ooId=PghPuQPwnnwzUPv@yL0Q%hW3oj)9szU+bXP%J{=Fh0y>5;zSsPW8eErq?QRj^UM^8z6Wmq^Pwnpeu2An!m2&N'
    'h9bfI&gnL@rr8@228r-`HMD^!AglWPt%i~R9;?3VGX-URXVz7CZ;2RVZjLbpBs4RotbQYHAQH&8Ysssl5CTy^w%LJKYo-lE0{O<N'
    '5ot}cH)3~(uxDn+9obM6n71suvAWsVKqQbYrz-o~<^&{E#QPzBV|AmkfhZu~J5DD@t!ef~jN>G>=ju7tge0Hc%Z5-}n9HyPlUN3|'
    'XfX#O@Kt1_g2N}qP>5jGp(kMWk?<t^i?0SB7IR@r(&&4$=%?XVn2tS+KM%S6Fpdg&XwSSLArJ{9l>0c>MDsM}X2}n(WnOYZ%xSLd'
    ';>Zbc^GFJ0#CKMR?<9yNtIN40xtz1|#tE_RD)@8_wfh(Haph$BGtJ(JNt`-$w8yiIkcWgZN#4GHyV?~<#Yq!l(QtOG6iJ@HlXJuB'
    'oiI7Uk&nOISR|VD8z;-Nm8@wl?k0t~QXh#^9Sl!{LMRH%l#wCHojZ*yn5N0;s|blmAhRP3Ig^|qGm_PcG_L{D=LDJ8B#@`(&gu!s'
    '2HJ#_!(`@2D5b@yM-?spJojSIW-vlTLj?bL2(|EqKS?!fILyL>!z;!pRQ<T<&mjv=hy@K{o%8xGLLd^zDu(6-R`=^Frh&|OeIcui'
    'hVjS>@koMr$vGijXnq;HCWacwjMtCj<!JvTM57^vQz2RXNOqg&L83w)4vY|ghS{AkZ{gbJ^jZjsNFa-r6JkMwSa!U27i=I3$UJuJ'
    'q}*pAZ6FfJytwg#gg_*aMVC0${_!+qv3bBNE@bn7N>a^9vU!j|cAOR<^NwT%@|ZC)Jd&*S9P2wL!<u9>;grNRtNXMKv;hfIkd%PK'
    'DSDW56vEh}d76!Z<|8<$Vi;v0Bn(IL24#9UEL;oajdJv+J~Sfmw35pE95PML&YgAkG$w>1!7Prf>L5>>mG-!duN5c6*NOtMNIBiA'
    '*EG8$w#|{%ZN>(ofPA@DtbQ3G4+SF(1!IJ`rr8^jQwLH>0$6h@7%ex?ut!DwS+BvwaI^RXmoVeh;8AThSmPo#ush9Zp|+}0_|V28'
    ';k=X&c%Lo>rw%R~iUzZWGb$ohk|e7<RhMu=+}w#lMXcjn!Rlqu1|os%nwA$N1R{ZSZ8EOJn~aMJ34>%GtRQV5638TlLX?k#<kZ4t'
    'Lv3J&%Q(R9l{ZU!ez;g>;rF_S^D8{5eXkFD&(mg>9t??7dXbY}bl@+OP(n|@FF(i3I@{yQtBuQsBEiggt>j)e&*{QtJT{yVj|~YT'
    's|B>{<^mcnV)M!g@n@R75x+y*x?sfkodU7p)OXb6B!nkU#d&L*{SiAT6*a6NNgll0^mJ#nCT;_fKo)VyuDZ;IBEc*xR&OwnhlH`_'
    'wDY>A*&VSfV2_K_t)}e?8pw_nBFX)_J8*iRUeoN3Se^Mzt%pz~mRC-zWNVt;5t|FI$y+uM4djiL;#NbekfT{(k7|qnZt<6J>3y+G'
    'Dw?Ga$BEAqG#UBY>(yce{J+J6HY8z;_IxFwP3iNUt=Ia*2ysobKVroSu_8fi5?;M;HV_G9%c&}AO|v&5r&|ljjpd$mdU;vX?2Y&+'
    'KMGcbqK}e-@x8e4y0zFq6p(QZXTY6Vozk<}o`4J4WGyd92t)yyoN{IddE_LFj}k6y=t^L9?gWIQz)W*iV{bPr@^BHa#|L~PkGzhb'
    'fKViu-H*$=l$zDNR-()Mo!4|n$V0)Hb?qCgM<5%B0y6JztR}#bELR*42VUPs8;An(RPq|xdfL3nOr{sp6oyL#|3~(b_6J{1(X<Sq'
    'iF`Hpz41*j^?Hc>VD9Ct$0^dYj`}&!I{3vTxGSeQM{AnB5#bn?3q1BDtlGA0C<;s%Yr|{F!UiINJaJkXU(@W3SQZ_xBYJEg3dpKU'
    'c^%_n15rRiZ*t1&_t6F-fqc7`yn0$85CvqL9e6bd+dw3cZ=71;)--z~c6SJS{&->aFm6LpVBWIq#_DEc1Cc<soEjBwEy-fV<L#YO'
    'jmpn7dn3k&_UzQ%T0L750D(3j$H)r}jNe)OVTQu+MGu}gF5ct?Q#iq4*FDsY2Vpo4FuEt27ntfZPk~aPJ_$L8!RL@rqvBl0$J3ab'
    'bt<@)dC3VeFG&!KBPYbo(-V*p-&rBPlOUesiq|~`0+B$LtbP|un%~8W)$d|O^1GOoH%^E(jM4l3ze4T)g?wB&S^iA3H)0Z}PMwMJ'
    'EF<J0VN8;@@87O=!Ax<|gjh739V<nWx54DxuzGq-PH<M{?=}{RX8p#=@@yq*nv1(h?L^_ksao-;K_L_cX3EHr<j$SO6^tL{^i@o0'
    'Ub55d2vfo(C&-NC9Wl*o$HuKc4Vl*@kOe2ht;ujx??;p8d!y3Q%tB6+?*(4eN1>h;HBBPwd*w+nh%t(K8G^R%RW$Y90-q1+7ld`r'
    '>LJnwB7v-8sBC6+o7p^X4;eD!^@Xf58pb0l#3KpfCFg{Aq4{O(niwk0GG0H9m!tiY5RHbkJ@NXH>^2Y5M1?#Y7$N=)vpZql!nMum'
    'Z3YsNKo%`0#DWH~?07AT+dveM+2eX}s-*c@NE?U(GB3J>6{HPB0@-m|?#Vln^`2vWXN0(>*&VT|YF3xD4MYKXO5&Q;-P#7CfrOJ%'
    'SUrS8A`-|nIXicj)YFy_iUhMbvZ_5hZPwa*D)Iu^OK3V$QRt0<3Zp>zL*V;^3HpB2p^^jODKDHB5zJ<u=V{b>o+fBa`ut>t(`&^E'
    '@wK8rEZXMC>Q-X|Q9!<2D^?dZ<e^}MaW{+**ED-0a_aghNdRk3^=0Me8R4jiRm{k6bJHJ}FymAYUTt;<<03Y&E68bCqN-B((8eO+'
    'ywos(J>ulKc}xW^B&U6?swE-p5>AGj8wjX~b$lyWy#m@mB#<qqr^YqS?ucE}^7=MHAQH%X8}ovMKopQLVe-KW(gq@dOj4M-{&A3;'
    'nq_P#63jz-`GLu4N5+OC!OVFrf?qdJLsFjhXFm#kKb*n^j!-aS@#bOZ15bLs7<8mU=tdgC2u{C-4K6qvTWF!jB^*aJEx(wFdu%u%'
    '9vc!wR%?&f&9z5d#O9R~;?FdDBYuYlVZn&;I|X9Hsa2-QNeEAzDje4|`y+NRY}BxV>?k1H^mJ#nonQlzKo)VyuBOa}BEjsS(vj8W'
    '-F5{HWXB4T<~Q<<Qx(seW^csq!0APBO|v^<b>=r_9YT><UO6rAtZ8;fY%X_JYmGJ#4djiL;*A3F^~9+NWlgg?VtwL-Sf6MRD^`fx'
    ')$_p=EVEuB<1bn+CYYrcie3i+Y;XC&I8S2Ku$`s+5IT=W4VznDG!F~>FODiQpCdL2uf{<ehy=3bR9LpA*&C75{rN@#c+WY#0j_EG'
    'MtqbX1*>x9M@hl>UR-$HT5KQ+$mEnW8&98;Fh0r-#^>d{rl~_H3e5C+d;sQ=*F10tMS|J>80>gpb<?q-NHDt}mw72QtFewmm-#!d'
    'A#jj~f-&pbH(oQ~AP@y)o?bg%GvFW)31oL;H3N?1ZTomQ@VcyRAPUISHRCjx=bBL<o==?Ce%3U5BbG(S>(m4rhy;?;c+7HZzj}mu'
    'ZocpL0Ze^cM6cka9XOpQ=mRjFMsG49>~DF#KP_+=&m4v-@T1X;vy9{n%F8c$)l*)>>1`ki$m`p+<khVOfhZu`?7*w-%?2WYe9Kvt'
    'JLVLKx0X}k?V4t9#K+q^r=6~!Y4%2pW0wwC*UuiX9&a764iAKS@)v)JhJG?qd!sjw%QDZN2X3~rdNh*`i~`PJfzt=ICxQj~t%dgB'
    'AAerY6Cc{MQ#Y5V9U%}6WcQIdwK4O&WJdy-b?%jdKW&-OSmq@s#JnUyERLKIH>ZFjBfhgjd?!JCVf9UXq4_43tbP+qn%~5V)i<#s'
    '`6g!NjT2(sRq*K=YWFYX?TwS=?TrNSe&&RDr+E>4uv(UQkSt3iaq84D9nUgC9umeRdHeqDdj5EkijyY9qT%dVDUz&7B<F_Jf@5+z'
    'X7DM*BGIflJ@>#tZ@>Rnq}?T(w1PQD39B_+8;S(e#kLQP*Y**Pdh(=+ydmlrDZE+t((lDQ!iLup$T1M}05v{P(F4<Q7h3@&XK2sX'
    'Qy&IunWxX|!5JB*B!F=ReIA^?ijar|GCO{xLUMx4jx>-Bv}u0il9y#ulVIkY79-P~<{MdXGAw8a>zviAjSWNsS;ZfTWOcvZJeUv}'
    'GUN4ytTGx#RyUZ6<_1%<dXK4T-efL0C&UZQ?Zw403L0;W0xIU=zzFeYnB57p(oR@^5uEmDY$y`Uy#2_WI&JG|$-E_jEIVEsH8v0h'
    'WcIiozHut7uz@Hb^P)>wLE1nhke9Y(b!po`8<1K@eeX@dtj8e;!w3fB>e=_z0!>I#i^(ivp8d%PDW^yT(=?1`3FWxVVc-w5_yy#H'
    'nd5_mvE#J(m~Wnlf{J*o?~D-FG`k}<Rn6)aV*^n@o|3p`_0wnr(Lln9QLNr)AQ1^<nw*_G$LwiK2t|Tf99h-po;JJUa2cH%!KKkg'
    'aN#1pR-6!DD+<J-ZH}z&*ESFZ<jb{U^~(r(C>YPo9(qXb(&vm*arl~Mcf=;|;JNY0>bcQ|qQK<TdQGz8SXP``kk&N2BeE(*DK|?|'
    'P!WGtv@tQ<EYHIw%s5@l)#i+&Ws#GCeXL&igQuf0oRu~@vP0g&rJwAq+aZ+mEGO90f)1p?9|NUE_y<00Z4JK|*xIxwR!g>3mBNQM'
    '776F2hPJJUljr6EQn-*UC&QM6uuC`@Zf^FYBG&P(V70Pi1Cc;>P0I@s0+B%8nK|C67-MdZF$Lr`N$m>HfmJi64Ml=^NH0GyIW3pj'
    'P$ZZ+uT7cjW^XGl<FVm{cx*@zSuL7fHy6!t5t~;|h(FWpj_BISG8*q>8C1ycFcn2Ga{Nw#*l_B|Y;qF96Q}y`HO=0LZF;)1S_ij*'
    'NFa;2WLGF^Lv3IJr5^f4hhp^LEJ8Jk-c!(gGz4=nd6O@c^rkTI0^v{E2v19){6Km}sZe?0FEDFP+k|VH-4Q#e0T+f7<YtcyGUUrg'
    'EJ9Y0FEo%HE5wcjk=3~Mc5~c1HX^Ux1RID1@{QAr%=YP+$cS&O5Z@>ey91|{#x>3Uh(}h4M-s&9%<n8h2t{If<+KU2rr8~_x!hSj'
    '?btvxkT+I}Hxk4Lr?<d0&EANwCr*W;Ynt5=%Z^tqlnq1zS)Vv5)+ZXoiWOo-g4iUyCdk-8TW9es3U;tyZd;%{3A<R!EW*$aCZ$C%'
    '!0@+F^;$%FQ1dK$81v@$q3?U1nBk-z>5KVu$d*$T{hDTPL{3kOHxj^{)1uCrW^cqhE5th$qCMyB#A+K5GEq=I%8!Coui&GkV0<qw'
    'ydHIIAPUIjlruY9G^b!p+a`ts5)P~`Z5xUN^H#^K>hf$L3dlUYcD%-aLm(2!?#61|GRgZ)QQvrtov?u@Aj_iTbx4^FL;}fa{&#t&'
    'AgsFd#Ok|f15rSB-GSFOb$1|Hx=pf%)lJ3*B3XTGIqg)hY4%2p5AE5htJ;6k(FWRp47B!#Ku-M_1;$tYqLw8ZMmT!M3}X;1y*A6B'
    '<RGRoRFMYFQ2Vpgb~2pl7xOt}*11<!_B7_^_%~e3yyS$Kmn4YC`XhC!-|cD0V@(2C962Fwo{E5s_|6LPodofP)i?2l=9^d^YhF)0'
    'CDHF<$?7g$(%hvhR+n@|a!F_9jT2(sRq*K=YWFXsQw^+7Ti$721|L^Wh(FWpjhMu#Q>X4c%LsW$7?X|@VnVVak<@RT5YO=08fkCI'
    'l#wIJ^_*r$Sl5x97&DTm#x&>j=$+;?hy^FZf`+ipSuIG|KpT*QkRdb)&C8^Fz|#E^=wavwG05Ji&>MxB<v2v6@_iGUUJlYXVu{9J'
    '@uyyV-d&Vd@kb&9PLi8v7$HMuyuOfCM#ISJ2D7=ggNs<RdScuhQH_gu$vGijNNz8Oth6&kUxZ?0X+x1<=Iuu&IqgnEA`-|F!g9J<'
    '+dveM+3l1<gUpLl4KmMS+E65zkL%$Zr;P*~hypS%x`Y*^4MYNYd9eDKggg|C$EK=TeIIQg3dmCu^D0BJfoLFMkUFa;Nk~KjSsYpI'
    'x1I`;1&h;b#R>7XqChOlir25B4MYN2=NEXZNhGHYLmP?&vu%#NzLgMY3(}j+Xq1V9QOiL`Ld((g-Y^BDoF-$Nj7AX#I-DXH17{+='
    '3}Wv4z`*%EzBl!sLcY{5j1<>2yCYsJR`+YjL&12?IF<ISX?90EaoVLhZ!el*B62FHFG&ComzLGygbhRjS#hcvUDNE2$ZF@htVw<o'
    'tC*4Db~O(w;h}tI_10nokw9jgeif^X<X5q3+7qjLbXBGBp^Zhtd8t2gR$JE9=9p1j$d;2K$x~z1C7cYm_o*=v>-bi%x?9^oB#>Rx'
    '@`8jwB#?Jzj&~}?n42TX`^+^-JE+4wu-ekHp*Aqp?0M5Lcm@vN34tk`r)bubA9_anQy@$j_S2-6Xo-5yGZNaA<UIMlQo{56;q&=#'
    '*F$>wfyt?W!iFNj%z14OUN?IRaT$*dC&Xhzf_N_Y%_D?RB$ljJa<7{!xwweU@xp51#|EN-d}XEhN`m-yEqUFmArJ-RcQ{f;Fmn7('
    'ftYb>6oxSHZ;(+qHk{gAo1BF3#A%|(nr3&z7gk@y7m{yco1X5h9vE#P63F@hGyXp^!D%##4Ml?4LA#MKoFuz~2C`#?NV0s}-p{-?'
    'XKWx6$Tv=R>^05)h;OVAw@T@w*@S_or*Trk*W)}(=r{^JAtJwrgLsx@2*<vUV3%tMJP{7s409iu+01}C`2Od|Y#lhg46bQ*N372L'
    'R=*(>iRG2kcFdY)cf{s$XLX~tfoLFatQ2n)h_5G3)sAbL-4V-<S3!>rL;_i#I4RaA8pMhfVnu@3B)rB>*gzzZEvHiOHO=0LoE~&Y'
    '9&_$Fr@Ear&HjiLY#y9M$cmEW_VOq{3Rb;ZkCKA%y}0nYOWQycka1EcypF<zKopS4iPs4pkcWct5WjIdzyl(|r}kfwJb(Xf&@jp@'
    'nuk7=<1|FWB1Wyf*;~drj6%O3mI=<LS;XW=V;?|=&7>DNz($8+9E=V>Z?;Kqb<C;=!v@;wTEc`Z>Km`VcN>TTvb=Mes&c0wymSSx'
    'IY~AU1!UJ9cx~!*2MWg5Bx_iGA8jBC$Xm^+rfN;IJ7UWUu_ZywJ5FWf`DTeEDq@^eaDRd6_AYh02T#AFS6erku^;@UmvV^YY@iCw'
    'h$s+V6pDVHr$EAAYQ4Z*XBjM>1W6N4@aLmmPf(iHd*kPrhxY8$&H8Cb2t)#zb?((xJ&n0J4Gq^aFF7IRB?;oOh7+-UPLRi%1hP1C'
    'Lfkz60~zt172-Py;tQ*9;tS0;u{_qio_I>4-^G&EUAm;XOINHe>5Al%&dM7n#Ja2C(>2uYU&#BJljWV}W$<z3g!nVf-iS$@I(3rI'
    'vy703gfZzjAtod%60Vi91Zbr!xQz81C&V*+wno}pGG*jQ^0Sy`M_3-?w1tpnBoE(d&gl&%-5l<^48tsymZDeFG>x7LJYz&4LNhIL'
    '4z*{5HwCl5c!5!a9K8RxyK~ub9aq-$yPWYxLA;65&=>iVwrnp+X=f(T+0cc0g&y_0cknFt>?mun5Du;%sM^@IT`1K5ZAzrbV0?bc'
    '20zRs*DQ!}{xifQ62qem!VA_M9RrDgtXGNEoBlD$Ma2{|$O>yf)|CuKs0pT)nP4tZE5^lU&Abq=J0yr#k?Cc-LOM2hrg=HU>P(HA'
    'zu%NWVp*MKVD8%QN+VTDP$CJCRkz#3QK^w?pkgQym>;+8KS*aWF^~kv-R^jYT8GC#A|Q|58frwwKqBkN+v*bvWDG>V?#`XaxV(N~'
    'J>S<435@%uzCex27)S!-VZFktFpGg?KvGw6sD(Kt5&?PKLzPk-mW!B6m$_hEuS%k0dOsK1_I*#6it-`%X6}hzrc6eEhne&=29@`H'
    '7+jH0*6879jPErP#P?bP;_<e>LA@PgAQ6ylv&RBSfh0h_-D;?}Bju66c&d<!d!A`t4H0Q?{44^nMk;rFrg=F;sMEsp;%Ol(#NR~+'
    'APg5PD0mT8NDp&ei9F18(;lGqb?SOUKgL)hIIoxQT~hr@|Cr}upG{tnEfT|41Yx&EVz_u3!wT`Tx*wswqhlZukX_SafuukpARk~H'
    'A5s`sXdFeB;dHu-b;240iGW;hIx3LbLbWc7p%!2|74$IW<zVUPicYrd<onDjI^>$mOpmjg=W#BSwu5rL4Yo98J``o2PvzWOUH%Mn'
    'ySe^1Or!(C7)k`@4(lx8ws?<=7vsJ`g1B!)AVTdv-WGQsc_B9YE7Yz}3?u{c9g5<+1jJw8Tcv<7{*r)LA>D(cF!T?oBsexmx44>}'
    '2*Lx>h4p8emqUDm8i;QqBeC5a9#HF?7)S)<@lM*aU*8*zbf++;5~0~q>9Q)3NOngVkR236k*%`!al$%Lh=D{vej-iT&or-x_z4B^'
    'QvzbQMfw_irg=HU`h+L#pim1edz)uN=7=U;FDhMcih@qLrlIVO@5!O54VijWaN``5pXe{jEEMG&M$>1eEd9?cZ%A9;&onQG*jyh_'
    '6LkzE1M&_<@h$?fdt9+bBL$KG`F=pEb$q6IImB~^Rn8LwiGaKukSJabG7xJhh_wjB7O8&unda3HA3LOSiN|8MEmnvh=kFubrH+rY'
    '1jeu96|4103?u<^wZ5#eEM*i(0_1k}iPp_}``^vB;(rS8+;sO9R_`(jBr-4`+uQ&CKmVMlG79OKFvgO=SvMD~ufrHf0_3$jwongv'
    '3?ws!C+Mm7e4hGZ)+UT}KI2U}#yc@|cV-?(P4{J7uV+82Fbz8QiqO#o8>f4hm!mSy6go45`nx>!p3hUy3o=Ddy=U{(^Ri6JQ}5Y4'
    '^}G<1^VEAbPdzWlq&)SW%~Q_|@e2y#mk7i+sFC<4GZItt)O$WpJu^tCS^6w9OV?13bS?5or{$^l+@5;g0hyGi-m`h?c_Aj{srPK2'
    'dRB<3dFnlzr=AyMQl5Ix=Bej}n3$*Dvw7-yF(&1y_q?8ZR+1Yajv}wc&H7sXgS6C%fkZ%7d)jA2I*Zv<%PQeApZqi{x(nm;+2nL7'
    '#`%66vq@`JxPflU=q!ZXXKE(PjP6ZVO#KjM)$7Uq3&<VPr{HEM1M!H&@F;`ug0<L*fkZ&otHesA{+Q%qyLx7j71n^PD;bPX6HF~L'
    '!Cau0-j|IC#On?T;#FjN*{+bzU!G}R4zW6)qgq`VB$m}#2Ij8)t~64~2_=#MS#`Tj9F-cWm@I}8f%$RULhba#KoTI6^VEAzPd(@I'
    'CpAyK=l9fej?2V6^`6mF&xx_2^H!R_kyb*KNd#qg>9B?*1(E={Z|V!wn=%HH0C`xiu&N$oprzJk-V8%O&2vWnnB0*|X6Un0k3$ji'
    'vhRo7(EX&m@SzA(HcSQGNXq;?(%&=8A!OlSKvDxzsBaufBm(ldhbr$mEEd-DVtlWWAimcU5RbS04eIR}1Brlan>`jt3M2vY?N&p*'
    '9Vw3l##4n<aP~~|YKTb33}+F5HBt%gGtJ8(LLI!Gm+fVo5P#QifG}JvM&U(RAwA4>CGs%WO?!aa*Qx6b{TO43;B1jlwjv0-H4?+c'
    'gDqBw$(iaspQ)Y~<l~IR@o|>H2sRuaLZh)=p>Y&hJ0|I=_k5muZ?v8BT>HuA88v~Mts16aj2~?1v)twb{poV8ve9PN&BZi0lLw#8'
    '+U3fdze=s{+0^R17?V<~dp5N?FGQ%#iDk7qFT~W;>Yh)n&J6M$isHKj#MIR4o=L6F3b8`EarCoVot0yQbYEsst<H<^fOIu@S*^|s'
    '@eOJqzR8TlE7FPTGtH|ZCg-R3e13XfkV*RKJ)fVRm*!<l{nWoJg>>ydh7y6<QLSxK7LPwB*&Ss-c2E#S_8Z&B3F|Z=1`+}JiL{7('
    'rg=TYPbi3=5)ivB(*DFV&Hs3)l?NR{;d~bQ$(5S=zfrHZxtP80by1eXV6uLm>1vU)YRYCimV+55J?3ug$Da?iy847?KA}(|EN@7M'
    'G0!wFhuB;nP!n|wBm?peMe!~HF)c^EXLHo^LQKt3@A(|{ydaZu)O$8ZJu}1_3Sun+u|+DlU3S#7LVT={AU@N)9O7pGy@G1BMTtZ}'
    '?vSdW9=nYM#E<j$Q58TOKh6>uzm8X|h9@zQ1jyC;vc~e|Q6LGBn^n_bb$z2iA|RW`7ONjP1rh<--B(y6k^)J9+-|Q}cM)PB36OPj'
    '!P@7Effhj0F;-q0)%&1|$!L`u+k0yIR(c=kyo)qErBnTA=CaRJNgdw2HAYQzIjMJQ?Cp;ruY08KG1o=IEic6G*h0M@V;~8T@9PR{'
    '=@SD<fV^Lj3VH5}O+|SjHc${75s0gGO^a}9g_+V-*5Z#p4eO<a_~`9C=2UAE+%Rc3xtYpKw05-e(Z#53Zu>l&lnsM5voHGI>rz{*'
    '3!9g&EPk#-S#8@>Qp=t{21$WLK<>^+6nAG4i2Dl}9UT(L#q}dE$m1Rf;$nkaW{6)<5WhqqzCn$|H<^)m-e0h0>9f##@eDOfpJit0'
    '8tRd*MIPzud`E(K>1z7*8S3Q&@^M09`H=a5`M4oL{J2R#T(34sHBbLjjFd+N<GMqFxb8$Co*Jk%<NC0#=vRs*Li6&8#PSqLUOr{U'
    '<z<gGFe#7($PExfk!dEmx~PJ$E@~{xY0#PN!&K<O(;Zd1uxhECVxEGxR7O#h{Zy#lxIUXFXN*&-?CEDZuPLX={S0z_t*}5+AQ6z;'
    '2h^*P@`zxp_H>SbbUwJL_97s6NLxLdoead|Wry`tQy>wL_3C@Ab0m_BCK+as71n^PWoB!rjqpt^^LD&Iea9>|u;zt$-627|icBxt'
    '>P+sF?>A+DSjJEyFn8^DrIAW`D3Juns@rYis7&gb@Sn1bp=4lQpeSBMAb#AoP`f=bkOauxv0FodjDbX!KeyE<*8U>}qF;CCPGnqO'
    'KcGGjDUS%ohKd1b5rnjyq)Z|xyGw^PB)i2MNOPE-AM-2^8Qq<+bVVjpeQC5W22IwtFsZ2+own3sG!Kf@aOE5vUA4)ltemI(XOMfO'
    '`p5lQ1YuKOpeCCbNCadHRV%e`B_JNwE3DG+7)S;rwfu+Lu%JXDAdh>f=lZaC`-m6gdyNF~y_SG@yzOsLZ^sx&1Z3M_745}95+L7h'
    'HPqXY@<?DjRY>Ky&or-wi1aNe@+o+(k?tux)4UuaQ~|(wu>gP-;_o^l5Qd9IQM?E%q=)&L=H(Di9oE@F3?u@wX%A4ljCH-CA7d;L'
    'oGlVck)6i6TO%=CJgM&ONC#G0mrBipSGx3W=yh4zqIY^$N>9DbRgo8N7_$(x8phzJu?%INSruJmKR~>6O$+sYjDbWzKF(MiA7>ei'
    'V8ihtG#c9#8po9c$mAN|7JQ9wSwY^`8>*Q2-a>WBjG;te?yxq$Z;Kb<cror9B#8S)1R~US*==#Vj2R--NW935#AbhmnyX_V8IbQ#'
    '6yGHv{`%f31%&aJ1jGvILMw%#e?TR{u|c|y+3Z9R9*#&14@VJ*Z%_mAO=cuskqRZAX<iMn-5efJi^Uj71my8fR?J`D8>o9lG1UUi'
    'BA7DJu~j)0rSW6LNy;}}WM-!S?6Zkl#0`@l`<c$Uym531$xQUG)Q__rjL(0jdD)Wx<hxQxU1ee@5ttp7(5n)OWOtMS*+D_<L?Av+'
    'SZ7-?kO;_6q($U2&Fdk4LP7kLfY@!3_9vccUJh}GbbzqjNQM_;efsBk{N5|1t~?Y<gk^KZ>UtXk$$-2=QM`*l{6yOAd8T<a#P<VI'
    'z3ns2%ORdStfI0QNCf2NfJE_fkbzi3L99g}wn#Pf&or-wNZxU*J4P{(1jxq<X*535yc{Cb=k#N_FRRX+^<^>lY6!+TH#j|-k&d~7'
    '&s640Z*<ugZVGl#6G?lVv*nl##W<A4X5nXu4b(_%)-n)J-+OJLK%OK(ejTq^J+)#W36QJxWsT*nra&SfZ&+=ND31ijO?O{m^$Dgx'
    '5+JuLx}A<RAY&jAklQQP)uI?k0_1g%)K%-5=G72y=MKvm90N&!Z0pSttM-HfNr1dxkSd|>i%q|IAvPV>Zkf!tOueN_(Q{H4s>?tA'
    'o~f72C&uMA8>l>a3fb73L63Tvv*5zyr<^v?#xU9}FEbT<o<-O4&<8X3gAQeIHvDW}UTxb`Qt!t<21$WLK<>^+6nAG4h{rt=#KnHq'
    '%n-kzAbyEJe1jT^Z!#nCyuV;gF6YJ1L1vIplgn9Ta;eUDB#4);reB|-UOpfnCnS~+nI+@L4GH4MO#<S2wMnXt|DR%{JR%q`pGXi-'
    '^xHGi%SoOtd#FWE3?u`x!Qyz>S8-UL8VQ;kAd(_)$jz#0{y|#x#6Th-*VhUQBn1)yxqU#rASsUs#%lk)QAmdgn@VKD-t3U}%r=Xy'
    'S@m4_zMs6dqoIy5^E6C~YLtVYteQ(_bE_t*ZMLNytfw=soKCt%YVKd;6CpJAXNbqk4(q9=Kq4UP)%RNGNF*0^Jj@^~tN~e9G8m!W'
    'j<w9&@dEW7v)FT)7vgn?1o0{|y=<#9c~8FIlmTKHLy5rLwck}z%I`lWxoagrR@8+hj!K;Yv8<L`%kaYdxNV^}Dq<iBkh^2Ih5{J_'
    'iOk%$)hE{083m$Wcjr!ITsCxeND~jz6i%5$P<EFN>MJn@k^s3!s`S~5tS0wOeSvyQ#y}z<Td2~Cy~vXMuwG#mLB>EbAgQS})JGyE'
    '5&?PKLp|4r#X9>rqh9~IcRrtjo5zw)xMo|pepYVq1vU8hx-fR=r&5JM_o2`8KBL31J`6(`-S9KU_ZkV}do2O+c-!Bg-i|Sl2*|d<'
    'Dm#mTBtX91YN)p(<&nU6s*nmwpJ`qWv2Bqcwygw2qz~$|2*B;Nh5DY3fkZ$aK9E+7O-nyMGrb&T-60Lgx)Xs2RZVeTtfpXv_`4_z'
    'gyCX^885;L>0y4Rc{#*}I>8~$(sjL|A7d;LoVN$o^`jU_1SHZYOf9l*th+T5!^PSOR*09bX`vqI7)S)<1B~NC3gZfm<I?KU%+~p0'
    '%#EA$WWqQp@-Hjh+iY}W5mXtB4Fu2R##`zZ*UuAORLZBhaBiIR&mgbe5o>!Q29f}ITW_d_=X(p)STBYWfw{vvj=3#fhvUV#Z;&AF'
    '8xe?5`#iVBeI90rP$TgoGZL@YGuCU70*QcZ-jOK&PV;JrzrMFh0b%?l0kJ~5)=FXMA5ckfY>+NxHaii7ha(ch!%+m{8`MC2lNpIu'
    'q^grfW{uNs4iBh}oft?2<nd1Sw_o2IsGDvvl?cttmXrzKl|t$*6GMr>?2wNBpJ`qW@o~aBl8J#tKz<^veV%Fl2Z&`x!X3Ik<O($y'
    'O&5yh(dD^!V^E`4<mH*@Vv)&xUb>;2LT~B(s|@jPER>n)U+iaypHL7#B_MWNq|fSSnwLY|A?<rFcR}HWc-(!jG}1O1B@zMI)N80&'
    'ItG#fd3}I^ygp<=-k~VoMIe44eZf4_yd2^u(tg=9&8s24ACO9IpJ`qW@!VmR<;6fEATI|bikE{7#2N}>EdsGcDxZI*c{Rke{NE*;'
    '|C<%!V}&#lpJ`qW5o%ZGA+xLVXrM-7BQg@dj#sSKZZVJq$kqCSwKWz4Er3*WuI6A|>D=t8aobEfo~anEQo0zYFb?HBl%;pn(9O7E'
    '^aEWn%I4CjX$V=-{|m?)RyQrmBY|;qJz_oBF^~kv?TRj?BY}*8BtY)YNVgB3X<iL+UmZ43qcH}O0C~7xw^%)GDUbxn)BU~r=W<+s'
    'pP)=-F_r|*>mI3d<1@{xA>Pg%R_Bu#NMtd-x}`&rj6i?56kjbZ#fe$3vW&{|hH1<PuV**sb8v&1XPcRE2r46X1lgClp&r)M$U2|Z'
    'ta4AC66WGxJ`HP{YN+wIMq){!L||^)Q%aBapM#`8A|Q8XB#OJU2*l$a3F2ZGdS-}UP!PXFAfERZtoP!1aqY+q66(Ep7I`mL=Q|R_'
    'OIOpc&rlpJ|MOp2UTAMJTD=!@AWw?Pv~fPmv(c8rSoU*JlOb&i{pJdrdpf0<@?jiY-cwVra{PHr-#?N5@3?=8ycixQB!~~0Rp$rP'
    '2jz#z2jzOTNy+c=#~3M(2*wN2TXB7&-=2|PPV#iwLoGgIAQ_Mi7RSTBio^2Mh|p}HSpH7)YKR*kgd)?-W_xL&9_koK2IK>b<3j{v'
    'wg28Iq_c=kwKQ3?epPRFNSnW#oead|Wry`tQy>wL_3C?_QVGVNlU!8!FoUeH24r2yV1#-*)-rF$3)J#^vF$Z4#On?T;#FjN*;Z$2'
    'd;R^U3=qp0N(APv{jRh_BDrftK;FKf=4#3#fw8)+>VJ?<w_+d>kRP`#7Dx&t0dlu(fha!Hyd2`OTSJY;7)WFVd0Tx#fsBFZ*WI}j'
    '8J7*6U(*5zX(>sWL{N5@4r&Dy14)3~BUSzFMZRkGO?`oSOU6J8AZ-|OI&>)}GYwfErhJ~fDRrTZ%Jo3)1?VTbdSeGVqv_S?%5j|C'
    'KtJ><Omt@RGsqUIyl3A^Ks>BhSOw8BkPOHp-Cc4}B#$B>k9(-+`mlIigcsv`jRf(%mVkIX*H~}I7)S)<ZGXc8Nr6N_whdMdX$&L*'
    '^6l~lMDdyC<q&T*)Lcz@Bru-9R*okTh!xU3g=d;qLqyu%Ig0?SJ0yg4Cjt?wp69$+&%+AwcUd3^!^Ij$UW66W!~9J1a)=FehD6%$'
    'uIml`7-Naxygjfkzr{czAdyNZ>cz^5Ves=<jKK~$Su+Rfd6xOf7o`nh9tTzQ*_@3g8;dDu*Sm5KWpBe+<WrdYBL5j-w?<;PTs6T7'
    '@zOO|7vEwa5s;5F7RSd~0^_wiwovnR3?u>aw%$<D$@dnjp<xUq0&|D8?R{ImN63nC-ylKUHzE*E$A6B;@4d>9Se}j|ETOh~Zp&A<'
    'cp*YP)fbtk`g+A$KgK{JAe(n2ioesm8se|-tx`Z3e@Q^BknUDf82SfP5*!<(o59Ua1mWR`#PA@pSZv;)2I8B{NW3B)@;5SToR(Th'
    '(&elT)a9&pxi2O!%+28ewc{8AE!j2mVaRpgn<@9&OeQbO-t>mdGvh#JO*2fc&wJ`;mZ>5Oiule&kvm-mPlC-s{S5MWC%fh^v|&l9'
    'L}*@+Dkz?5UJr3gBAV|?<xniQClQz(Qa#Eu&C4M|HK=bNCn1Pfht@HW2*^*QPnu_%S3~T!NTuJ;G%ts^Lpq6hrg=HU=8DyQIR=se'
    'd55BS7lHVRwAJ%W^J<9i2c$yLXPTEoJa;Ro_hJkr0`hV|qIfyTK&+u4)*=vFq~h;qnpZ=7tdJl+)4Uua)R)Uc=F8>LK#jy^aU_O#'
    'g5^sym9sN*q3FI)S<ZBGh<dk$S(#x7*5`gG%E4usDa`DAuL_s>Fpl~BGsF(->yPqCVEj5>vD)s$KoTJL)nNk#G6s?WdAMG;SZ(qs'
    'kOatPyX~OP`ePsoknQz+$10k*E{elhLEg{Z6$)ewBmr`@uIU{~t&CE-@239LT}`1DU^=RHifTbUPKt0*J78PRy~+ECa|~{D!Ovwu'
    't%98$0@Y8IV^L(Y>t~~LU+AA<ZuV*2M)+fpo5gm^ydbyj2@50z5&^k8BT?MRjK<?03F2aFTV{w~P!PXFAfERZtoI@Xk^u?zUOdaZ'
    '7cW&>pM`(S@v_)$ix=brisD0Nsq=9|g7|ThfVf_5lIjiorx+=Z2*%4N62uezwtUTqm*nZPhg$K(Kr$d3ERKhL6^G@i5uw>Yv23mq'
    '5H~;wMW&g}_5t-wQyvkF)&6^<kT$?KmB<{k*&%I|ZFVvckCz?RQ%!*uKq{^Ckkg6PkPjxa134Kr{q->B6EzX06E9UvB`F<e6|%l8'
    'hO)4IC~dsVPWHyp{tU8SeXn(nL~^mCIy1-$Ye3eO3`VH8W4#xFc!63qF18-zg?QZ|LA;7gFWc%&hyCAg$^fy9p+sQrT9T$aB$B&U'
    '0%Uc*LmkL;HT_yG7Mby~ysc`e^Q{<21mwqUiv^MbNr2pKTOf+hG%tsE?AB1DF$NM@M&4GRP#|L<`gM2iM8;)9XRovhLRwE!CJB^#'
    'r0Sl%$clX5kVPHo;f{esK(<g76?>66`><YN6+Xs5A|Q`@sNr}xiflt3-fJX??~9*>%GiP~qnESEj0q)q8~t3&MwKDhV3Z2Iol2ke'
    'qgG{Ujq0<)8#Rx!H?!5_j}VV-gH_uT14)2<yVXz+HRX}On3jxQvB~IpA=XDEi1kqdBGTu}Sp;C+At9_g5r|M{t>@*lR!)fZ3W(uy'
    '{Ru0=3h804E0Kq}ZrTIXeokF)=*JjK1n2F6RZkxSiGV~p(W+Y!gxwm6;qqY?C&WwFv``Op3?u^bfz<<r@<?F3cE=WKzK($;K&B?4'
    'S8Nh`UW`de=oOoUo);q27xhi%i#jcFx?&TjkJIS-QMqE$S!rio^o8nkMOTb;mi0>I{p|JV$9}d$F%Kah9a$Z9>4sv6w~hWTak}CY'
    'r}KhLN}R6P#ObUMQxm5vCUH6|#0u$p(a+*^R*ntQ<(NfrIxoTl(jnloIGq>b8`MC2lNpIuq_fmUW{s1iI9>6H(|KX0CQes;;&fh+'
    'Ns7}IpE#YDW{S>l#pnFyh1nsUST8%jc_Drxt$&s+%ghizp&*J(*=bpp6`N(57h-CbWyNP%W(IkOqIj2pn3f<|u?d2CA*Ln>R(yis'
    'Fcvn`zV~I&R!v?7t+U*Xc9@FMIOn~x-sVH5=OUlRex$2KWtoMdC}*vv{x1>)D>gweFT@t93~JeJ%L*|qx2<Ax+www$S}!iUZFwO!'
    'P$RLC8HpX%ntR!8%Zl-9-C!+rVjvNasY!wrpCp(S<f`tldXvRK5+IYaEh|3TGBe0K6vev)#MAw~`sZ?7f1jWlSI1ZqIFs`&D?Z;c'
    'E6C)0%Zksp%sX$VrU=%2ir~D+sM*dq2k%somu6JOsC(<E4^J`V-s>SN-B`}qG+S~g^u}thGuKo59Xrpx`nwdtnokkT3o<E1ux3*P'
    '^FmBY5v<u1!ORf9pdfyUKuk>$toand%pjrOi)WelVrq(D&8G<F1^IxY_>fuZB&7(}Y>Hr3h^Z-pHJc)s7h_V2V9l!t<|Ub$B3Sb&'
    'f|)@!SRDUN5zI@ofnvF+2<C<OfyD4b0^tUTpvX*}nq^tDS(bS*CTCgJY?ftSkUONk#%0SgFT~U=%bL%!?E1pFJhzsL!E=?DR@1qb'
    'w!tek=}~3A&x>IgoSJ>+9Q{#J@ptY9TPUad%>8ASWzA+;W(HYd4ah~yGBZY~x8tH^nHS;(YSp;dr;Hb3QkG@SW?ANin3`iyb2|oE'
    'aV9CP)_l@xUYN;At2LXnniXV)G-dzXx$KWQ{^!3+rA--J7&7apk!)o{KlNU#+&QP{vuKKaH?{ND_Jb+x(D$RsGU~TEYokY9{zd+9'
    '&Fv589oDJ&!!@5joE2nR+H1|Gz2=3uJKmu_Fk>JQkg55@HJ?A6733bNz-lkD1WnG;toba>ydYbsqL#hL6qB5#S@T(%c|j&-Y1Vv}'
    '=01#*r~Wg2U*zMYy`qzy5VAZrpCL6s;f6dAJD<^2oS~m{HHA!*r`ftG8;bESvNUTxOEV|L<Sfma(bCKbGBr!H=Cd?&Vob}@toba>'
    'tPqp3G;2OfGbco(&zG|Zz@#kAn$ObA3K8n8_6JKdC&Z*I&6>^9%!;r=dYFH(G_yiX&C;ydEzPVrQ?oQ{MoTj*NTdUpWlJ+F!lW$C'
    'n$ObA2{AcKvu3n3vx0nJwW0aJ(#(l5IZLx<v@~;qOwH1)`7F(>7?ZLzYd%XeD@3R->SaqaYav-$mS)XnY37BPnx$FuS(<r4CS_^X'
    'Y?fwLh^bkcHIt>86=H*QDP++u%!}}Vba=IF7v_cd1~m}hWJY4WMS}P{&C4NPkq%NDnFUUAR$<L&73Kw5ZLxMDVjvNaDGG%(pHP?='
    'W@?S>HD4opUXUHqDfP0MnHS<G(%Ny^%*+ZgEvc|(lM3@fOie1R`J}?kAn#BVMJAWDq{5m{Dm+YiInQ|(MpyRJpiEiJlQyJ732qov'
    'pAFtRZL%-~qY3RePE%?6c^E=D73JS071n%GVP23)Nrg3=RG1fHi&V9<EEQ&jn4CRI^Vy?VL8fJA)@*iWUWiZ&?`1nPFT@6FBsMZ5'
    'vBUa!S++B?Voc7?toiKBydYDvGiyFOGb_mC?97_a&ddrjEvc|(lM1s!JnlQH+(GJ7NQops(xC;`?SmLd<f|I#y5+mf?#>E}p$Np}'
    'Y|Mtw#_aUuhtkfODzhS}nXC!H`i%C!$KLe)WT(t#V^J2?Oj+SFGlkNdd{l!iZ3y|_Wn(scHfCOsN!geUn~j+lVp29{!)9Y<hWG^q'
    '@k<0^YBpxWXJcjt3H4q)%e)s;voRY!8#6D+8`Lv>yNW=3Kn=x*%z7~?rL|#GTC+k-O=)e|l-9f$lTun6UZpiJ$<&nAhEHkD46?!E'
    '_-{&UUYZRQ%SL3`la$iha4D@>5pIA8ip<ohDXk5g(wY}za!PB%rnKe-xkK8pT~=BvpF28~%I)Zb%V%BqU_%~M=`8&ZHkg9^5Pmkw'
    '7bYjywNkEh{Zt04%E9K--=(xRd`fFxkcpX?4V#IX86(s~UCTVw7pTR~a(8c5h)J244V#IX7h-BAX2We_X2rQ(QKxUDStbS&0hyxG'
    '+VCl@d0{4}v^H!?YhIA&4r}Kz29f|-AuS?*c7yYBOiJu+xW(SQEK?JE8$Pi&FUaPI^{E{LiGb{o&aa<oUJWrhL%QKJr1OGI&5&;R'
    '4C$;O_ee#Ldyy}i<P7PC&ydawvW2RVS~R5R-m1YXoAu?`mzh^X{L}Z2t{qu37KIwdVVH|B=sceaKe;@VLzbB_^tsmA-(^TQe1>#h'
    'kck=64VxjI7h_U}bi-yyXN8!YA>Hs9(pf>KW=J<|hICepX&KTDn<1SSVp4{5!)8clg^2X|auxxYlp)=)8PZuHCMEYaTyk$-gcZ^_'
    'T$X$DLQGBWZMfy$yf{;ndmBEvH!sK*38KipPFiwr!zTA;g_xY&+wjS~SwSXer8az4YF3b`S*Z=1m6{i0QdVliW~JtZ2vrHbY^5%A'
    'X+mG<!g)VY54Up89C^J*Z|B+NiYy($8ApF8JE&ZZ!)WO2stCphWk>rrS*Z=1m6{h~YF28)XQk!^nUs~<uvw{DA*N=fHcVD(R)`JK'
    '1(`)FH7~+9D28t`5R(!r8#bXbFT^X-xl1E6Hzy}lHhe;5UXUqzfDNAqm=|Vh9$>@g0p<nSAsuKfdw_W%ej+V-mOa3%5YzGi8#WIx'
    'FT@+tlINM`<q%VoDH}eSGBe0K6h)C4IxU&9VUsEILQGAjZ1`l#ydaa3DH}GKviCL%VNydMRB%2kotkx)<;IMrAG|AdZikUB4yh~{'
    '(@!S&c_1&k9R@#)z5k13%7#s*%nC6r2e4st0P{kGT68ZvfO#P{P$RLC8Hp{@4XkIHmqYBZK3tYX%B&cZ6Db=$kuodD<ov&e&;QE`'
    'a<~21VRe$AKoTGi*9+F89Ro>#Oi!k4*ksDAAd{0R8$Ovb?_{&OrB#k+|8%lhE$)9$ed&uSn{w^_tc{w&Fj!NDqRjeHc}I=uwWhzM'
    '4WEJjFpl)VWDD+RL)801{S0z_S!02uKq4Sh(<)m&tuimj)U?W$PpixeGAXUHWz#D2LQG1lY}vHR%n-kzAbyEJOiin7`LxQ+Afeui'
    'XPNh6YFcH>r&Z<!d4qbU7q!Z~5SyyS8jTc41mpvX;zMTPos^&2viYf5A*SZ1wrqZCUW`fksV%RcnwMm1ern6-r{)FOKv8T&Ry;`='
    'l`WT1nHAv%h~U!Pl2aFSve>FplcLsA4~|Ux+3TXWllF$HL~TLx+EDgBOwMRZVwEL>?QF-apY`}Nz*YMR^+t?=L_j8{rnYQqYF>=V'
    'si`fSnwl5n4r$YSSxwCgF*P-{<x^Ahf=o<JZQ0b+%ow2_>RRTZzCf)SFEZ=Kq}0@wO-;=UF*P-{<yKR(;!I9WZTZyHydYClQ(HbY'
    'H7m>tY0Cat1kB4ZDG{*c76J3JOicuA`9#3HAX5_oTRssmFUSt*pm13P%nR}3w#9m^DUbxn<gRa7zUy1OAX8IQTRt^49c5*9DoQ_C'
    'uX^7P&W~EnbC`zS^+V}gaHCgKIpo$BIUR15lPO(M1U-i`n7>O+ZTZyHtRVLl5X5~YgYXW;P~?H$BNZ?&-ZJ7vn3^Kp@+s1JLAFq3'
    'dW(v5R*1<d(k-7Nofl+cige4SNaw|vTIU4I*g1g}WKynq%jTMAg?L<_8mQ421Brkn$2}HE3M2uNB==C$4CRr)_|)8kKzycoImF+Z'
    'dlZPj)4UoY(g(H3_w;#t#kzqR1Brk<Al>XZkPP@g|3A~qQPv&OfUG+ai0|ijs5N5@v;dOYl@TdD7Cy6XEDN3aVASm9(%RC8v6%Zj'
    'D@tRBLXFN@T^3=~GqE1L)}#Gdm%ajmSg%A7R!9$Yz1VPq7h*$|jz}|gU2o{e7)u1_?SZv95d(>UY>^<gA_%)R62rwqepZN=u4$nj'
    '=om-><h46ueG<k%5+H9otX<pN;)P6JjQa)&;$CEyzMVU)<xUJF0ut&b;cf9IAu~j%NBSZ&60cXR&ebuH2*~CgiDDzNP4<gS6AB39'
    'FA0bZ(go{gCxY+|is73K#CnSav0l1R<aM9*`7jit(R9c{!c{wy*Tm(0k&i0mWnP#*6ohjc$;q1gaw?0$xxp$`X6j!cUXf0xo5i`A'
    '6=J(NJfJosVjvNamo4czzAKd@!K6?kFgv6Jt!J8-L;OUVsh??H4YAuHZAWy=a$r`7H>8=myNS%yT~lKj$zmWGkk<zo$m>G}<Q<CQ'
    'T>|3!0qK1IndapX&mGpitQbfH<mG@w@p2G>*dmpiJkz`y;=QWwP#Y65kO;^I>0A1l=G71%E2KyIndapXp}wUbGT+jV25KZWA|o+5'
    'O}gXLq>qL5z0aNQ3+g?lTxm+W{*n#T5Q;)gUWeHlW$EwA>Hf=5s@@Q8LP>{MlN!U{rAc>unsi=}scF(3pC+9bWNMmp$EQi>1(}p4'
    '-LYxXc_AjHNq20TbY_TOP!PXFAf~2CcYK<3W{^<t#k0(NF*QxP<I|+`g1kXJ(~FvPUWln_(jA{BofqT-isD0N;hmHw-LYxXSs|vT'
    'Nq20TbY6_9$-Nz)+?y9<Qoeb|>zn5#*+7lQMr6g4lqTJAY0_B{Zh#1i%q_`j(jA{BJyT|O)PyWIrtF8HOM*z?=4r^Mo;r`IEO=|Z'
    'SJ^mvQ|Qtc(>#|dr{k^31p8NM(jA*7ofl(rnsmpeN#_N*L)!FS)}-@7Oih#S_%!LfAQRK1J2p)^Ge)R~x|VsUFHoz-#pWiw5R=lR'
    'J2p)^FT~U|>5f~I&WbZRO}gXLr1OGIQIqcYH0i7`E2Js=XH7aU$D}mrj$4z?%Q7{)x8t*W^MdS<&bOBB-n<Y~vwJ%}yEiMy<m}##'
    '&+g3&vLY856v(O(`PNQOlkWI5>AWCQ)1*5-O?n6>@70+5+|sooP4|dgR+dE`tQjWjb&<JZwmn@(@`f6~6*dcD&i(9*p%{if{5_g<'
    '$E8VUMtFx}co%_)RKUDHiy%x*lkWI5>AWCYs4~5MD*-V%O}gXLr1OGIOq1@|H0it;Q`4k7K216=$fPvsj!l!!3NblNy5rNN^MXuG'
    'lkWI5>8v1A)1*5#O*$*av^43CO_R<GF)2;DW7DLwLPYwY7Wtk|OG)k6l+?TsQ&UnqP9-%X$fT6ij!#L=iLgR?pnp<Qb3#nbq3rk^'
    '%40t$ZEa!7plmi|HZL-g>`>n~6Usag*{M{erh7<gwj=%boSMMpvG<#?<lUM7F1NSic6;;UY>`m5A_$XGQad&!H7msAl+=z-NzDuL'
    '0mktmg>i+(aU}sVHM6&4Gkf!5Ov>!-*v#I%5K}XIJ3g~FFG#4%Z_8$HW{6Oa^hIVQCMBeHY(i>Qh^Yyw9g~on6=Jj9V)em{fkZ$e'
    '-3eYad-EcEgJSq512HMHw_`JV^Fq8L9jGpwy;&h9XZCh{W^Z1Q7o_9BcCnIChr9?=K5Cnnb6HMmQnMa)G1ILfx;~_c+U#eSkEJW;'
    'BJ{mBnRA67^Raim8vZ^#y5rNM^TO<q4p*1;=)4f2dR4a%nUVO3v}Rm(%(FsF%Q5fR9P_*oQ?q(IKC3q~$U79py9mS&q#62|=G73>'
    'QlmRIH99ZE)YRyXPmRtCGAT8>V^gE^LTr)Bo|e_<tPqn^qdPt|IxoluX_j7Aqq9OxOO5W>)abkrp*{g0GM|8HsnH#q8l4wni*)7u'
    'ndapXJFLA3%EO28fBoP82O{cRWd'
)))
def duration(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"

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

def column_key(column):
    # HeaderType.NAME may include inline field parameters and .value.
    name = str(column).split("|")[0].strip().lower()
    name = re.sub(r"\([^)]*\)", "", name)
    return name.removesuffix(".value")

def find_column(frame, name):
    matches = [i for i, column in enumerate(frame.columns) if column_key(column) == name.lower()]
    return matches[0] if len(matches) == 1 else None

class Client:
    """Same working public SDK interface, with durable raw responses and ETA."""
    def __init__(self, ld, root, retry_empty=False):
        self.ld, self.root, self.retry_empty = ld, root, retry_empty
        self.db = sqlite3.connect(root / "recovery_raw.sqlite")
        self.db.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, request TEXT, payload TEXT, retrieved_at TEXT)")
        self.logs, self.calls, self.seconds = [], 0, 0.
        self.started = time.perf_counter()
        self.phase, self.done, self.total, self.failures = "", 0, 0, 0

    def start_phase(self, name, total):
        self.phase, self.done, self.total = name, 0, total
        print(f"\n{name}: {total} jobs", flush=True)

    def call(self, rics, fields, parameters, label):
        request = {"universe": list(dict.fromkeys(rics)), "fields": fields, "parameters": parameters}
        encoded = json.dumps(request, sort_keys=True)
        key = hashlib.sha256((VERSION + encoded).encode()).hexdigest()
        cached = self.db.execute("SELECT payload FROM responses WHERE key=?", (key,)).fetchone()
        frame = None
        if cached:
            payload = zlib.decompress(cached[0]) if isinstance(cached[0], bytes) else cached[0]
            raw = json.loads(payload)
            frame = pd.DataFrame(raw["data"], columns=raw["columns"])
            if self.retry_empty:
                # Template names/descriptions are metadata, not financial values.
                positions = [get_position(frame, fields[-1], ["STD Income Statement All", "STD Balance Sheet All"])]
                has_value = any(position is not None and (frame.iloc[:, position].notna()
                                & frame.iloc[:, position].astype(str).str.strip().ne("")).any() for position in positions)
                if frame.empty or not has_value:
                    frame = None
        entry = {"request_key": key, "phase": self.phase, "label": label,
                 "source": "CACHE" if frame is not None else "SDK", "status": "", "error": "",
                 "fields": json.dumps(fields), "parameters": json.dumps(parameters), "universe": json.dumps(request["universe"])}
        self.done += 1
        print(f"[{self.phase} {self.done}/{self.total}] {label} ({entry['source']})", flush=True)
        before = time.perf_counter()
        if frame is None:
            stopped = threading.Event()
            def heartbeat():
                while not stopped.wait(15):
                    print(f"  Waiting for LSEG: {label}, {duration(time.perf_counter() - before)}", flush=True)
            thread = threading.Thread(target=heartbeat, daemon=True)
            thread.start()
            try:
                for attempt in range(2):
                    try:
                        self.calls += 1
                        frame = self.ld.get_data(**request, header_type=self.ld.HeaderType.NAME)
                        if not isinstance(frame, pd.DataFrame):
                            raise TypeError(f"Expected DataFrame, got {type(frame).__name__}")
                        self.failures = 0
                        break
                    except (TypeError, AttributeError):
                        # A programming/SDK mismatch is not an unavailable company.
                        raise
                    except Exception as error:
                        entry["error"] = f"{type(error).__name__}: {error}"
                        transient = any(word in str(error).lower() for word in ("backend", "timeout", "timed out", "429", "503", "502", "504"))
                        if attempt == 0 and transient:
                            print("  Transient/backend error; retrying once...", flush=True)
                            time.sleep(2)
                            continue
                        frame = pd.DataFrame()
                        entry["status"] = "REQUEST_ERROR"
                        connection_failure = any(word in str(error).lower() for word in (
                            "session is not opened", "session is not open", "connection refused",
                            "no proxy", "unauthorized", "401", "403", "10061"))
                        self.failures = self.failures + 1 if connection_failure else 0
                        with (self.root / "errors.log").open("a", encoding="utf-8") as stream:
                            stream.write(f"\n{label}\n{encoded}\n{traceback.format_exc()}\n")
                        print("  " + entry["error"], flush=True)
                if entry["status"] != "REQUEST_ERROR":
                    entry["error"] = ""
                    self.db.execute("INSERT OR REPLACE INTO responses VALUES (?,?,?,?)", (
                        key, encoded, zlib.compress(frame.to_json(orient="split", date_format="iso", default_handler=str).encode(), 6),
                        pd.Timestamp.now(tz="UTC").isoformat()))
                    self.db.commit()
            finally:
                stopped.set()
                thread.join()
                self.seconds += time.perf_counter() - before
        entry["status"] = entry["status"] or ("RAW_SAVED" if not frame.empty else "EMPTY_RESPONSE")
        entry["rows"] = len(frame)
        entry["seconds"] = round(time.perf_counter() - before, 3)
        self.logs.append(entry)
        # Persist the small log too; the raw cache is committed before parsing.
        if len(self.logs) % 25 == 0 or self.done == self.total:
            save_text(self.root / "request_report.csv", pd.DataFrame(self.logs).to_csv(index=False))
        remaining = max(0, self.total - self.done)
        eta = duration(remaining * self.seconds / self.calls) if self.calls >= 3 else "estimating"
        print(f"  {entry['status']}: {len(frame)} rows | elapsed {duration(time.perf_counter() - self.started)} | phase ETA ~{eta}", flush=True)
        if self.failures >= 6:
            raise RuntimeError("Six consecutive failed SDK calls. Stopped to avoid running a disconnected/denied plan; completed responses are saved.")
        time.sleep(0.15 if entry["source"] == "SDK" else 0)
        return frame, key, entry

def get_position(frame, field, aliases=()):
    for name in [field, *aliases]:
        pos = find_column(frame, name)
        if pos is not None:
            return pos
    return None


ROW_COLUMNS = ["ticker", "ric", "template", "requested_fiscal_year", "period_end", "date_status",
               "provider_field", "definition_id", "numeric_value", "raw_value", "request_key",
               "parent_request_keys", "currency_requested", "reporting_state_requested", "review_required"]
DEFINITION_COLUMNS = ["definition_id", "provider_field", "provider_title", "provider_description", "role_hint"]


def validate_plan(plan):
    allowed = {"TR.F.IncomeStatement", "TR.F.BalanceSheet"}
    seen = set()
    for job in plan["jobs"]:
        request = job["request"]
        if len(request["universe"]) != 1:
            raise ValueError("Embedded plan must contain exactly one RIC per call.")
        template = request["fields"][-1]
        if template not in allowed or request["fields"] != [template + ".fieldname", template + ".fielddescription", template]:
            raise ValueError("Unexpected fields in embedded plan.")
        params = request["parameters"]
        if not re.fullmatch(r"FY\d{4}", params.get("Period", "")):
            raise ValueError("Expected explicit FY period from the original request.")
        if params.get("ReportingState") != "Orig" or params.get("Curn") != "USD" or params.get("Scale") != 0:
            raise ValueError("Embedded parameters differ from the original extraction.")
        key = json.dumps(request, sort_keys=True)
        if key in seen:
            raise ValueError("Duplicate request in embedded plan.")
        seen.add(key)


def role_hint(code, description):
    # Match actual codes or the provider's TITLE only. A description of EBIT
    # mentioning revenues/expenses must never make EBIT a revenue observation.
    known = {
        "tr.f.totrevenue": "total_revenue_candidate",
        "tr.f.totrevbizactiv": "total_revenue_candidate",
        "tr.f.cogstot": "cost_of_revenues_candidate",
        "tr.f.costofoprev": "operating_revenue_cost_scope_review",
        "tr.f.sgatot": "sga_candidate",
        "tr.f.intrexpn": "net_interest_expense_scope_review",
        "tr.f.grossprofindproptot": "gross_profit_candidate",
        "tr.f.totassets": "total_assets_candidate",
        "tr.f.shholdeqcom": "common_equity_candidate",
        "tr.f.shholdeqparentshholdtot": "parent_equity_including_preferred",
        "tr.f.ebit": "operating_profit_context",
        "tr.f.incbeftax": "income_before_tax_context",
    }
    if code.lower() in known:
        return known[code.lower()]
    lines = re.split(r"\brepresents?\b", description, maxsplit=1, flags=re.IGNORECASE)[0].splitlines()
    title = lines[0].lower() if lines else ""
    if "gross profit" in title:
        return "gross_profit_scope_review"
    if "preferred" in title and ("equity" in title or "stock" in title):
        return "preferred_equity_component_review"
    if "minority interest" in title or "non-controlling interest" in title:
        return "minority_interest_component_review"
    return "statement_context_unassigned"


def parse_statement(table, job, request_key, definitions):
    template = job["request"]["fields"][-1]
    ric = job["request"]["universe"][0]
    instrument = get_position(table, "instrument")
    name = get_position(table, template + ".fieldname", ["name", "fieldname"])
    desc = get_position(table, template + ".fielddescription", ["description", "fielddescription"])
    value = get_position(table, template, ["STD Income Statement All", "STD Balance Sheet All"])
    if any(pos is None for pos in [instrument, name, desc, value]):
        return [], "RAW_SCHEMA_REVIEW"
    rows = []
    for record in table.itertuples(index=False, name=None):
        if str(record[instrument]) != ric:
            continue
        code = str(record[name])
        if not code.lower().startswith("tr."):
            continue
        description = "" if pd.isna(record[desc]) else str(record[desc])
        definition_id = hashlib.sha256((code.lower() + "\n" + description).encode()).hexdigest()[:24]
        title = re.split(r"\brepresents?\b", description, maxsplit=1, flags=re.IGNORECASE)[0].splitlines()
        definitions[definition_id] = {"definition_id": definition_id, "provider_field": code,
            "provider_title": title[0].strip() if title else code, "provider_description": description,
            "role_hint": role_hint(code, description)}
        raw_value = record[value]
        numeric = pd.to_numeric(raw_value, errors="coerce")
        # No silent date inference from the requested FY label.
        for ticker in job["tickers"] or [""]:
            rows.append({"ticker": ticker, "ric": ric, "template": template,
                "requested_fiscal_year": int(job["request"]["parameters"]["Period"][2:]),
                "period_end": "", "date_status": "ACTUAL_PERIOD_END_NOT_RETURNED_BY_TEMPLATE",
                "provider_field": code, "definition_id": definition_id,
                "numeric_value": None if pd.isna(numeric) or abs(numeric) == float("inf") else float(numeric),
                "raw_value": "" if pd.isna(raw_value) else str(raw_value), "request_key": request_key,
                "parent_request_keys": "|".join(sorted(set(job["parent_requests"]))),
                "currency_requested": job["request"]["parameters"]["Curn"],
                "reporting_state_requested": job["request"]["parameters"]["ReportingState"], "review_required": True})
    if not rows:
        return [], "NO_MATCHING_STATEMENT_ROWS"
    return rows, "PARSED" if any(row["numeric_value"] is not None for row in rows) else "NO_NUMERIC_VALUES"


def write_summary(root, client, rows, completed):
    log = pd.DataFrame(client.logs)
    statuses = log.status.value_counts().to_dict() if not log.empty else {}
    text = ["# Single-company retries of failed LSEG statement batches", "",
            f"- Finished plan: {completed}", f"- Original failed batches: {EMBEDDED_PLAN['failed_batches']}",
            f"- Single-RIC jobs: {len(EMBEDDED_PLAN['jobs'])}", f"- Jobs processed this run: {len(client.logs)}",
            f"- New SDK calls invoked: {client.calls}", f"- Statement rows parsed: {len(rows)}",
            f"- Elapsed: {duration(time.perf_counter() - client.started)}", "",
            "| Status | Jobs |", "|---|---:|",
            *[f"| {status} | {count} |" for status, count in statuses.items()], "",
            "Only universes from the original failed whole-statement batches are queried.",
            "Fields and parameters are unchanged; each call now has one RIC.",
            "No old output folders are required. No unrelated extraction stage or price download runs.",
            "statement_rows.csv contains amounts/text and FY request labels. Actual period ends and publication dates are not fabricated.",
            "field_definitions.csv contains the exact full provider definitions referenced by definition_id.",
            "All rows are review candidates, not approved Fama-French inputs. A role hint is not an equivalence decision.",
            "The compressed raw-response cache preserves original table columns and values.",
            "Repeat this command to resume; failed calls are retried, successful/empty replies reused. --retry-empty rechecks empty replies."]
    save_text(root / "report.md", "\n".join(text) + "\n")


def run(args):
    validate_plan(EMBEDDED_PLAN)
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    plan_json = json.dumps(EMBEDDED_PLAN, sort_keys=True, ensure_ascii=False)
    save_text(root / "embedded_request_plan.json", plan_json)
    jobs = EMBEDDED_PLAN["jobs"]
    print(f"LSEG STATEMENT RETRY {VERSION}\nScript: {Path(__file__).resolve()}\nPython: {sys.executable}", flush=True)
    print(f"Output: {root}\n{EMBEDDED_PLAN['failed_batches']} failed batches -> {len(jobs)} unique single-company jobs.", flush=True)
    print("No previous output folder is required. No unrelated extraction is started.", flush=True)
    if args.plan_only:
        print("Offline plan saved. No LSEG request sent.", flush=True)
        return
    import lseg.data as ld
    if "header_type" not in inspect.signature(ld.get_data).parameters:
        raise RuntimeError("Use the working Python 3.12 / lseg-data 2.1.1 environment.")
    print(f"LSEG library: {getattr(ld, '__version__', 'unknown')}\nOpening signed-in Workspace session...", flush=True)
    client = None
    rows, definitions = [], {}
    completed = False
    try:
        ld.open_session()
        client = Client(ld, root, args.retry_empty)
        client.start_phase("SINGLE-COMPANY STATEMENTS", len(jobs))
        for job in jobs:
            request = job["request"]
            label = f"{request['universe'][0]} {request['parameters']['Period']} {request['fields'][-1]}"
            table, key, entry = client.call(request["universe"], request["fields"], request["parameters"], label)
            if entry["status"] != "REQUEST_ERROR":
                if not table.empty:
                    parsed, entry["status"] = parse_statement(table, job, key, definitions)
                    entry["parsed_rows"] = len(parsed)
                    rows.extend(parsed)
                else:
                    entry["parsed_rows"] = 0
            if len(client.logs) % 50 == 0:
                write_summary(root, client, rows, completed=False)
        completed = True
    finally:
        if client is not None:
            try:
                print("Saving statement rows, provider definitions and final report...", flush=True)
                save_text(root / "statement_rows.csv", pd.DataFrame(rows, columns=ROW_COLUMNS).to_csv(index=False))
                save_text(root / "field_definitions.csv", pd.DataFrame(definitions.values(), columns=DEFINITION_COLUMNS).to_csv(index=False))
                save_text(root / "request_report.csv", pd.DataFrame(client.logs).to_csv(index=False))
                write_summary(root, client, rows, completed)
            finally:
                client.db.close()
        try:
            ld.close_session()
        except Exception as error:
            print(f"Session close warning: {error}", flush=True)
    print(f"Finished. Read {root / 'report.md'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "lseg_statement_retry_output")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--retry-empty", action="store_true")
    try:
        run(parser.parse_args())
    except KeyboardInterrupt:
        print("\nInterrupted. Completed replies are saved. Re-run the same command to resume.", flush=True)
        raise SystemExit(130)
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
