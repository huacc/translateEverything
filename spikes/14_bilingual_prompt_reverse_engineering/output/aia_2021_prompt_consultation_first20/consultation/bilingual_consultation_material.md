# 双语 PDF 咨询材料

## 任务目标

- 当前系统正在做上市公司年报 PDF 的中文到英文翻译与高保真回填。
- 我们已经有一版人工英文 PDF，可视为“目标风格与目标表达”的强参考。
- 这次不是让模型直接翻译，而是让模型反向分析：提示词应该如何设计，才能更接近人工译文效果。

## 当前已知问题

- 当前很多 prompt 仍然混入了对翻译本身无贡献的信息，例如页码范围、章节类型标签、过长的邻近摘要。
- 标签类 prompt 经常上下文过重，正文类 prompt 的上下文也有明显噪声。
- 我们希望把“真正应由模型处理的内容”和“应由工程层处理的约束”分开。

## 当前 Prompt 样例摘要

### label

#### system

```text
你是上市公司年报标签翻译助手。
语言方向：Traditional Chinese -> English。
只负责翻译当前短标签或小标题，不负责排版、回填、压缩。
保持短、稳、正式，不要扩写成解释句。
输出必须是 JSON，且只能输出 JSON。
```

#### user

```text
任务
- 语言方向：Traditional Chinese -> English
- 文档场景：上市公司企业年报
- 公司：AIA GROUP LIMITED
- 当前页面：10
- 当前输入单元：短标签 / 小标题
翻译要求
- 保持短、稳、正式，不要自由改写。
- 不要把短标签扩写成解释性句子。
- 不负责排版和回填。
页面上下文
- 当前章节：Chairman's Statement，类型：chairman_statement（页码 10-11）
- 术语使用模式：heading
- 上一组摘要：在2019冠狀病毒病大流行期間，
- 下一组摘要：持續為數以百萬計的客戶
当前标签
- unit_id：p10_b10
- 原文：
我們的同事關懷社群，克盡己職，
输出格式
{
"translations": [
{
"unit_id": "p10_b10",
"translation": "<译文>"
}
]
}
```

### body

#### system

```text
你是上市公司年报正文翻译助手。
语言方向：Traditional Chinese -> English。
只负责翻译当前正文语义组，不负责排版、回填、压缩、分块。
允许在当前 group 内恢复断句和语义连接，但禁止跨 group 补写、删写或改写事实。
必须遵守术语锁定和事实锁定。
输出必须是 JSON，且只能输出 JSON。
```

#### user

```text
任务
- 语言方向：Traditional Chinese -> English
- 文档场景：上市公司企业年报
- 公司：AIA GROUP LIMITED
- 行业：Life Insurance
- 报告类型：annual_report
- 当前页面：10
- 当前输入单元：正文语义组（group）
翻译要求
- 只翻译当前正文组，不要承担排版、压缩、分块、回填职责。
- 可以在当前 group 内恢复断句和段落语义，但不得跨 group 补写或删写。
- 保持上市公司年报文风：正式、稳定、可出版。
- 数字、百分比、货币、年份、专有名词必须准确。
- 如术语锁定与原有表达冲突，优先遵守术语锁定和事实锁定。
页面上下文
- 当前章节：Chairman's Statement，类型：chairman_statement（页码 10-11）
- 术语使用模式：table
- 上一组摘要：由於2019冠狀病毒病相關的控制措施對新業務銷售造成影響，新業務價值下降至27.65億美元。我們迅速採用
嶄新的數碼工具，提升業務運作效率，加上近期放寬外出限制，帶動銷售動力強勁復蘇，並延續至2021年初。
- 下一组摘要：稅後營運溢利增長5%至59.42億美元，產生的基本自由盈餘則上升7%至58.43億美元，反映我們擁有高質素的
經常性盈利來源。內涵價值權益創新高，達672億美元。截至2020年12月31日，集團當地資本總和法覆蓋率為
374%，足證我...
文体与偏好
- Use US$ for U.S. dollar amounts.
- Keep listed-company annual report disclosure tone formal and publishable.
- Do not change numbers, percentages, years, named entities or financial metric values.
- Use established financial abbreviations for table labels when provided.
- Keep row and column semantics unchanged.
术语锁定
- 新業務價值 => VONB [context_term]
事实锁定
- percentage_15: 15% -> 15%
当前正文组
- group_id：p10_b21
- group_bbox：[73.7, 614.71, 313.21, 626.66]
- 原文：
與去年同期比較，2021年首兩個月的新業務價值增長15%。
输出格式
{
"translations": [
{
"unit_id": "p10_b21",
"translation": "<译文>"
}
]
}
```

### table

#### system

```text
你是上市公司年报表格翻译助手。
语言方向：Traditional Chinese -> English。
只负责翻译当前表格单元，不负责排版、回填、压缩。
保持表格语义和顺序，不要改写成正文。
输出必须是 JSON，且只能输出 JSON。
```

#### user

```text
任务
- 语言方向：Traditional Chinese -> English
- 文档场景：上市公司企业年报
- 公司：AIA GROUP LIMITED
- 当前页面：20
- 当前输入单元：表格单元 / 表格行
- table_role：row
翻译要求
- 保持表格语义，不要改写成正文句子。
- 尽量保持原有行结构和顺序。
- 数字、百分比、货币、缩写、括号位置必须准确。
- 不负责排版和回填。
页面上下文
- 当前章节：New Business Performance，类型：business_metrics（页码 20-21）
- 当前章节：Group Chief Financial Officer's Review，类型：cfo_review（页码 18-30）
- 上一组摘要：小計
3,053
57.7%
5,219
4,427
66.6%
6,585
(31)%
(31)%
- 下一组摘要：未分配集團總部開支的
稅後價值
(161)
無意義
無意義
(154)
無意義
無意義
無意義
無意義
当前表格输入
- unit_id：p20_b16
- 原文行数：10
- 原文：
為符合合併準備金及
資本要求所作調整
(103)
無意義
無意義
(87)
無意義
無意義
無意義
無意義
输出格式
{
"translations": [
{
"unit_id": "p20_b16",
"translation": "<译文>"
}
]
}
```

## 双语页样本

### Page 2

#### 中文原文摘录

```text
目錄我們的目標
我們的目標是 概覽
006 財務摘要
協助大眾實現健康、 008 主席報告
010 集團首席執行官長久、好生活。
兼總裁報告
財務及營運回顧
016 集團首席財務總監回顧
040 業務回顧
056 風險管理
062 監管及國際發展
064 我們的團隊友邦保險簡介
企業管治
友邦保險控股有限公司及其附屬公司 友邦保險提供一系列的產品及服務， 069 董事責任聲明
（統稱「友邦保險」或「本集團」）是最大 涵蓋壽險、意外及醫療保險和儲蓄計劃， 070 董事會
的泛亞地區獨立上市人壽保險集團， 以滿足個人客戶在長期儲蓄及保障方面 078 執行委員會
覆蓋18個市場，包括在中國內地、香港 的需要。此外，本集團亦為企業客戶 083 董事會報告
特別行政區、泰國、新加坡、馬來西亞、 提供僱員福利、信貸保險和退休保障 096 企業管治報告
澳洲、柬埔寨、印尼、緬甸、菲律賓、 服務。集團透過遍佈亞洲的龐大專屬 110 薪酬報告
南韓、斯里蘭卡、中國台灣、越南、 代理、夥伴及員工網絡，為超過3,800萬
汶萊、澳門特別行政區和新西蘭擁有 份個人保單的持有人及逾1,600萬名團體 財務報表
全資的分公司及附屬公司，以及印度 保險計劃的參與成員提供服務。
125 獨立核數師報告
合資公司的49%權益。
132 合併收入表
友邦保險控股有限公司於香港聯合
133 合併全面收入表
友邦保險今日的業務成就可追溯至 交易所有限公司主板上市（股份代號為
134 合併財務狀況表 1919年逾一個世紀前於上海的發源地。 「1299」）；其美國預託證券（一級）於
按壽險保費計算，集團在亞洲（日本 場外交易市場進行買賣（交易編號為 136 合併權益變動表
除外）領先同業，並於大部分市場穩佔 「AAGIY」）。 138 合併現金流量表
領導地位。截至2020年12月31日，集團 140 合併財務報表附註
及主要會計政策 總資產值為3,260億美元。
265 內涵價值補充資料的
獨立核數師報告
269 內涵價值補充資料
其他資料
295 股東參考資料
298 公司資料
299 詞彙
附註：
(1) 本報告所使用的若干詞彙的解釋和縮寫已列明於詞彙章節。
```

#### 人工英文摘录

```text
OUR
CONTENTSPURPOSE
Our Purpose is OVERVIEW
to help people live 006 Financial Highlights 008 Chairman’s Statement
Healthier, Longer, 010 Group Chief Executive and
President’s Report
Better Lives.
FINANCIAL AND OPERATING
REVIEW
016 Group Chief Financial
Officer’s Review
040 Business Review
056 Risk ManagementABOUT
062 Regulatory and International
DevelopmentsAIA 064 Our People
AIA Group Limited and its subsidiaries AIA meets the long-term savings and CORPORATE GOVERNANCE
(collectively “AIA” or the “Group”) protection needs of individuals by 069 Statement of Directors’
comprise the largest independent publicly offering a range of products and services Responsibilities
listed pan-Asian life insurance group. including life insurance, accident and 070 Board of Directors
It has a presence in 18 markets – health insurance and savings plans. 078 Executive Committee
wholly-owned branches and subsidiaries The Group also provides employee 083 Report of the Directors
in Mainland China, Hong Kong SAR(1), benefits, credit life and pension services
096 Corporate Governance ReportThailand, Singapore, Malaysia, Australia, to corporate clients. Through an
Cambodia, Indonesia, Myanmar, extensive network of agents, partners 110 Remuneration Report
the Philippines, South Korea, Sri Lanka, and employees across Asia, AIA serves
Taiwan (China), Vietnam, Brunei, the holders of more than 38 million FINANCIAL STATEMENTS
Macau SAR(2) and New Zealand, and individual policies and over 16 million
125 Independent Auditor’s Reporta 49 per cent joint venture in India. participating members of group
insuranc...
```

### Page 3

#### 中文原文摘录

```text
友邦保險一覽
全球唯一一家總部 在香港聯交所上市、 百萬圓桌會設於香港、於香港上市 香港註冊並將
註冊會員人數並100% 總部設於香港
全球之冠專注於亞洲 最大的公司 唯一連續六年
的國際人壽 問鼎百萬圓桌會會員
保險公司 人數之冠的跨國公司
為超過 業務覆蓋 於2020年內，我們已支付
3,800萬份 逾160億美元
個人保單的持有人及逾 的保險給付和理賠，
1,600萬名 為客戶提供必不可少的 財務支援
團體保險計劃的參與
成員提供服務 為亞洲大眾提供保障， 18個市場
總保額接近
2萬億美元
2020年報 001
```

#### 人工英文摘录

```text
AIA AT-A-GLANCE
The only international life THE LARGEST NO.1insurer headquartered and
listed in Hong Kong and LISTED COMPANY WORLDWIDE FOR
100% FOCUSED ON THE HONG KONG MDRT REGISTERED
ON ASIA STOCK EXCHANGE MEMBERS
which is incorporated and The only multinational
headquartered in Hong Kong company to top the table
for six consecutive years
Serving the holders of PAID MORE THANmore than PRESENCE US$16 BILLION38 MILLION benefits and claims duringindividual policies
2020, providing vital financialand over IN
support for customers
16 MILLION
participating members of
group insurance schemes Provides protection 18 to people across
Asia with total sum MARKETS assured of almost
US$2 TRILLION
ANNUAL REPORT 2020 001
```

### Page 10

#### 中文原文摘录

```text
概覽概覽
主席報告
在過去一個世紀，友邦保險
於亞洲區內，為極需我們服務的
社區大眾提供保障而備受稱譽，
這令我們引以為榮。
謝仕榮先生
獨立非執行主席 在2019冠狀病毒病大流行期間，
我們的同事關懷社群，克盡己職，
持續為數以百萬計的客戶
提供無間斷的支援。
友邦保險在亞洲歷史悠久，源遠流長，經歷各種社會動盪和不明朗時期仍能妥善管理業務，因而贏得卓著的
聲譽，體現友邦保險誠可信賴、強韌穩健，並堅持為持分者做對的事。自2020年初以來，2019冠狀病毒病大流
行導致營商環境不斷變化及日趨複雜，而政治、宏觀經濟及資本市場亦出現前所未見的轉移。在這樣的環境下，
友邦保險的財務實力，以及「幫助大眾活出健康、長久、好生活」的目標，更具重大意義。本人衷心感謝友邦
保險所有員工、代理和合作夥伴，即使面對最嚴峻的挑戰，他們仍關懷社區，克盡己職，專心致志地為客戶、
其家庭以及我們的社區提供支援。
由於2019冠狀病毒病相關的控制措施對新業務銷售造成影響，新業務價值下降至27.65億美元。我們迅速採用
嶄新的數碼工具，提升業務運作效率，加上近期放寬外出限制，帶動銷售動力強勁復蘇，並延續至2021年初。
與去年同期比較，2021年首兩個月的新業務價值增長15%。
稅後營運溢利增長5%至59.42億美元，產生的基本自由盈餘則上升7%至58.43億美元，反映我們擁有高質素的
經常性盈利來源。內涵價值權益創新高，達672億美元。截至2020年12月31日，集團當地資本總和法覆蓋率為
374%，足證我們雄厚的資本實力和嚴謹的財務管理。
董事會建議派發末期股息每股100.30港仙，增加7.5%，反映我們的財務業績穩健強韌，同時董事會持續對本集團
未來前景充滿信心。這使2020年的全年股息達到每股135.30港仙。董事會秉承友邦保險行之已久的審慎、可持續
及漸進的派息政策，讓本集團可把握未來的增長機遇，並保持財務靈活性。
008 友邦保險控股有限公司
```

#### 人工英文摘录

```text
OVERVIEWOVERVIEW
CHAIRMAN’S STATEMENT
AIA is proud of its reputation
built over the last century in Asia
on being there for our communities
when they need us the most.
Mr. Edmund Sze-Wing Tse Our colleagues have
Independent Non-executive
Chairman responded to the COVID-19
pandemic with care and
dedication as we continued
to provide uninterrupted
support to our millions
of customers.
Throughout AIA’s long history in the region we have managed our businesses through many periods of change
and uncertainty, earning our company a reputation which is synonymous with trust, resilience and doing the
right thing for our stakeholders. From early 2020, the COVID-19 pandemic presented an ever-changing and
complex operating environment and we witnessed unprecedented shifts in politics, macroeconomics and capital
markets. AIA’s financial strength and Purpose of “helping people live Healthier, Longer, Better Lives” has never
been more relevant. I am immensely grateful to all of our employees, agents and partners for their care and
dedication, remaining steadfast in supporting our customers, their families, and our communities, through this
most challenging time.
New business sales were affected by COVID-19 related containment measures, with value of new business
(VONB) reducing to US$2,765 million. Our rapid adoption of new digital tools helped maintain business activity
and, together with more recent easing of movement restrictions, led to a robust recovery in sales momentum,
which has continued into the beginning of 2021. VONB for the first two months of 2021 grew by 15 per cent
compare...
```

### Page 14

#### 中文原文摘录

```text
概覽
集團首席執行官兼總裁報告
2020年業績摘要
友邦保險中國業務在2020年為本集團新業務價值帶來最大貢獻，並在2021年初表現卓越，與2020年同期比較，
今年首兩個月錄得非常強勁的新業務價值增長。儘管2020年的9.68億美元新業務價值較2019年下降17%，但這主
要由於2019冠狀病毒病在首季爆發初期新銷售有限所致。年內稅後營運溢利增長14%，主要是由於我們日益增長
的有效保單組合及有利的理賠經驗。
在2020年，我們成功獲得監管機搆批復，將上海分公司改建為中國內地首家外資獨資人身保險子公司。於2021年
3月，我們已獲得中國銀行保險監督委員會批復，准予在四川省開業。四川省是中國內地以國內生產總值計的
第六大省份，以人口計為第四大省，為友邦保險帶來重大的長期增長機遇。
香港在2020年2月初實施旅遊限制，來自中國內地訪港旅客的新業務銷售實際上已經停頓，導致新業務價值大幅
下降。與上半年比較，我們的代理分銷來自本地客戶的業務於下半年錄得雙位數字的銷售增長，維持顯著的市場
領導地位。夥伴分銷渠道的新業務價值顯著低於2019年，乃由於透過零售獨立財務顧問渠道的中國內地訪港旅客
過往銷售比重較高。稅後營運溢利增長10%，受惠於續保保費強勁的增長及有利的理賠經驗。
友邦保險泰國業務在下半年錄得非常強勁的表現。儘管新業務價值全年下降4%，但隨著外出限制放寬，按月表
現已展現正面動力，而下半年新業務價值較上半年錄得33%的增長。
新加坡業務下半年亦有卓越的好轉，與上半年比較，新業務價值上升56%，按年則上升12%。新業務價值全年
下降5%，由於我們的境外夥伴業務受到嚴格的邊境管制措施所影響，抵銷代理渠道的增長。稅後營運溢利上升
8%。
馬來西亞方面，新業務價值全年下降13%，特別反映在上半年嚴格執行的外出限制。下半年新業務價值回升，較
上半年增長72%。
其他市場方面，下半年的新業務價值較上半年上升10%，其中南韓和印尼的回升幅度正面。整體來說，新業務價
值全年下降4%，主要由於新西蘭、菲律賓及印尼錄得跌幅。其餘的市場均錄得新業務價值正增長，其中越南、
中國台灣及印度在2020年較2019年錄得雙位數字增長。
代理渠道方面，我們轉移使用線上招聘和入職培訓的趨勢，支持新入職代理及代理主管人數錄得雙位數字增長。
雖然疫情大流行期間面對面會議受到限制，導致新業務價值下降28%，但隨著限制放寬，加上各業務採用新的數
碼工具，新業務價值在下半年已強勁回升。正面銷售動力延續至2021年，與2020年同期比較，代理業務在首兩
個月錄得非常強勁的新業務價值增長。
中國內地訪港旅客的旅遊限制影響我們的零售獨立財務顧問業務，導致夥伴業務於2020年的新業務價值下降
41%。我們從銀行保險帶來較為堅韌的業績，並為此渠道的新業務價值帶來大部分的貢獻。我們與印尼的Bank
Central Asia (BCA)、泰國的Bangkok Bank Public Company Limited（盤谷銀行）及馬來西亞的Public Bank
Berhad（大眾銀行）的銀行保險夥伴合作，在2020年均錄得新業務價值正增長。
012 友邦保險控股有限公司
```

#### 人工英文摘录

```text
OVERVIEW
GROUP CHIEF EXECUTIVE AND PRESIDENT’S REPORT
2020 PERFORMANCE HIGHLIGHTS
AIA China became the largest contributor to the Group’s VONB in 2020 and delivered a successful start to 2021
with very strong VONB growth in the first two months of the year compared with the same period in 2020. While
VONB of US$968 million for 2020 was 17 per cent lower than 2019, this was mostly due to limited new sales
during the initial outbreak of COVID-19 in the first quarter. OPAT increased by 14 per cent for the year, primarily
driven by growth in our in-force portfolio and favourable claims experience.
In 2020, we successfully obtained regulatory approval and completed the conversion of our Shanghai branch
to become the first wholly foreign owned life insurance subsidiary in Mainland China. In March 2021, we
received approval from the China Banking and Insurance Regulatory Commission (CBIRC) to begin operations
in Sichuan. Sichuan is the sixth largest province by GDP in Mainland China and the fourth largest by population,
representing a significant long-term growth opportunity for AIA.
In Hong Kong, the introduction of travel restrictions from early February 2020 effectively stopped new business
sales from Mainland Chinese visitors, leading to a significant fall in VONB. Our agency distribution delivered
double-digit sales growth from our domestic customers in the second half compared with the first half and
remained the clear market leader. VONB for our partnership distribution channels was significantly lower
than 2019 due to a higher historical mix of sales to Mainland Chinese vi...
```

### Page 17

#### 中文原文摘录

```text
財務及營運回顧
016 集團首席財務總監回顧
040 業務回顧
056 風險管理
062 監管及國際發展
064 我們的團隊
2020年報 015
```

#### 人工英文摘录

```text
FINANCIAL AND OPERATING REVIEW
016 Group Chief Financial Officer’s Review OVERVIEW
040 Business Review
056 Risk Management
062 Regulatory and International Developments REVIEW
064 Our People OPERATING
AND
FINANCIAL
GOVERNANCE
CORPORATE
STATEMENTS
FINANCIAL
INFORMATION
ADDITIONAL
ANNUAL REPORT 2020 015
```

### Page 19

#### 中文原文摘录

```text
大流行病對我們2020年財務表現的主要影響是對新業務銷售的影響，原因在於我們眾多市場的遏制傳播措施限制
了面對面的銷售活動，尤其是在2020年上半年。儘管2020年的新業務價值27.65億美元較2019年減少了33%，我
們迅速採用了新的數碼工具，並且外出限制的普遍放寬支持了銷售勢頭的恢復。友邦保險中國業務為2020年本集
團的新業務價值帶來最大貢獻，也是我們第一個顯示銷售勢頭有所恢復的報告分部，原因在於該地區自2020年3 概覽
月逐步放寬嚴格的封鎖。撇除維持低位的中國內地訪港旅客銷售額，本集團其他分部的新業務價值在下半年強勁
復甦，與上半年相比增長了23%。本集團的新業務發展勢頭在2021年持續強勁，首兩個月新業務價值較2020年同
期高出15%。
截至2020年12月31日的內涵價值權益創下新高為671.85億美元，於派付股息19.97億美元之前增加52.77億美元，
原因在於內涵價值營運溢利72.43億美元抵銷了政府債券收益率下降的影響。內涵價值營運溢利包括來自正面營
運差異5.49億美元，原因在於與我們的內涵價值假設相比，我們的整體經驗持續維持正面。我們的高質素、經常性盈利來源以及對有效保單組合的積極管理，帶動稅後營運溢利增長了5%至59.42億美元， 財務及營運回顧
並使營運溢利率穩定在16.9%。所收取的續保保費增加了10%，經常性保費總額佔2020年所收取保費的90%以
上。稅後營運溢利增長受益於全年顯著正面理賠經驗，其抵銷了新固定收入投資的收益率下跌及假設長期股權投
資回報減少的影響。一如預期，上半年所述的異常正面醫療理賠經驗並未在下半年再次發生，但我們繼續看到此
來源對稅後營運溢利增長的正面貢獻。在友邦保險泰國業務的失效經驗恢復正常的情況下，下半年的續保率有所
改善，而本集團的續保率為95%。
產生的基本自由盈餘為58.43億美元，增長了7%，是由我們有效保單組合的持續增長和我們對此積極管理所帶 企業管治
動，這足以抵銷預期投資回報降低的影響。於2020年12月31日，本集團的財務狀況仍然十分強勁，於派付股息
19.97億美元後，自由盈餘為134.73億美元。
於2020年12月31日，我們的主要營運公司友邦保險有限公司（AIA Co.）的償付能力充足率仍然非常強勁，為
489%。於2020年12月31日，在新的集團監管框架下，集團當地資本總和法覆蓋率為374%。日後，我們將披露集
團當地資本總和法覆蓋率，作為衡量本集團監管償付能力的主要指標。
董事會建議末期股息增加7.5%至每股100.30港仙，並須於本公司應屆股東週年大會上獲股東批准。這使2020年的
全年股息總額為每股135.30港仙，較2019年的全年股息總額上升6.9%。這是秉承友邦保險行之已久的審慎、可持 財務報表
續及漸進的派息政策，讓集團可把握未來的增長機遇，並且保持財務靈活性。
我們仍然對友邦保險在整個亞洲地區的業務機會充滿信心。我們將繼續專注於投資資本，以實現具盈利的新業務
增長，並運用我們的競爭優勢，同時維持審慎的財務管理和實現長期股東價值。
其他資料
2020年報 017
```

#### 人工英文摘录

```text
The main effect of the pandemic on our financial performance in 2020 was on new business sales, as
containment measures in many of our markets limited in-person sales activity, particularly in the first half of
2020. While VONB of US$2,765 million in 2020 was lower by 33 per cent compared to 2019, our rapid adoption
of new digital tools and the general easing of movement restrictions supported a recovery in sales momentum.AIA China became the largest contributor to the Group’s VONB in 2020 and was the first of our reportable OVERVIEW
segments to show a recovery in sales momentum as the country emerged from the strict lockdowns in March
2020. VONB for the rest of the Group, excluding sales to Mainland Chinese visitors which remained minimal,
recovered strongly in the second half with an increase of 23 per cent compared to the first half of the year. The
Group’s new business momentum has continued strongly into 2021 with VONB for the first two months 15 per
cent higher than for the same period in 2020. REVIEW
Embedded value (EV) equity reached a new high of US$67,185 million at 31 December 2020, increasingby US$5,277 million before payment of shareholder dividends of US$1,997 million as EV operating profit of OPERATING
US$7,243 million more than offset the effect of lower government bond yields. EV operating profit included AND
US$549 million from positive operating variances as our overall experience has continued to be favourable
compared with our EV assumptions. FINANCIAL
Our high-quality, recurring sources of earnings and the proactive management of our in-force portfolio...
```

### Page 20

#### 中文原文摘录

```text
財務及營運回顧
集團首席財務總監回顧
新業務表現
按分部劃分的新業務價值、年化新保費及利潤率
2020年 2019年 新業務價值變動
新業務 新業務
新業務 價值 年化 新業務 價值 年化 按年變動 按年變動
百萬美元，除另有說明外 價值 利潤率 新保費 價值 利潤率 新保費 （固定匯率） （實質匯率）
香港 550 44.7% 1,138 1,621 66.1% 2,393 (66)% (66)%
泰國 469 71.0% 661 494 67.7% 729 (4)% (5)%
新加坡 330 63.4% 520 352 65.5% 538 (5)% (6)%
馬來西亞 222 59.9% 369 258 63.1% 406 (13)% (14)%
中國內地 968 80.9% 1,197 1,167 93.5% 1,248 (17)% (17)%
其他市場 514 38.4% 1,334 535 41.9% 1,271 (4)% (4)%
小計 3,053 57.7% 5,219 4,427 66.6% 6,585 (31)% (31)%
為符合合併準備金及
資本要求所作調整 (103) 無意義 無意義 (87) 無意義 無意義 無意義 無意義
未分配集團總部開支的
稅後價值 (161) 無意義 無意義 (154) 無意義 無意義 無意義 無意義
扣除非控股權益前的總計 2,789 52.6% 5,219 4,186 62.9% 6,585 (33)% (33)%
非控股權益 (24) 無意義 無意義 (32) 無意義 無意義 無意義 無意義
總計 2,765 52.6% 5,219 4,154 62.9% 6,585 (33)% (33)%
儘管2020年的新業務價值27.65億美元較2019年減少了33%，我們迅速採用了新的數碼工具，並且外出限制的普
遍放寬支持了銷售勢頭的恢復。友邦保險中國業務為2020年本集團的新業務價值帶來最大貢獻，也是我們第一個
顯示銷售勢頭有所恢復的報告分部，原因在於該地區自2020年3月逐步放寬嚴格的封鎖。撇除維持低位的中國內
地訪港旅客銷售額，本集團其他分部的新業務價值在下半年強勁復甦，與上半年相比增長了23%。本集團的新業
務發展勢頭在2021年持續強勁，首兩個月新業務價值較2020年同期高出15%。
友邦保險中國業務在2021年錄得成功的勢頭，首兩個月的新業務價值與2020年同期比較，錄得非常強勁的增
長。2020年新業務價值9.68億美元較2019年減少17%，主要由於2019冠狀病毒病在第一季爆發初期而導致銷售額
有限。隨著外出限制放寬，新業務動力得以迅速改善。新業務價值重拾我們慣常的季節性規律，比重更側重於上
半年。在2020年，友邦保險中國業務為集團的新業務價值帶來最大貢獻。
在實施旅遊限制後，友邦保險香港業務來自中國內地訪港客戶的新業務銷售自2020年2月初起實際上已暫停，導
致其新業務價值大幅下降。新業務價值利潤率錄得跌幅，反映新業務量減少導致承保開支超支、產品組合變動及
利率下降的影響所致。澳門在2020年9月底恢復中國內地旅客個人遊計劃。這為澳門的中國內地訪澳客戶銷售回
升提供支持，使其在第四季佔友邦保險澳門分公司的年化新保費總額超過三分之一。
018 友邦保險控股有限公司
```

#### 人工英文摘录

```text
FINANCIAL AND OPERATING REVIEW
GROUP CHIEF FINANCIAL OFFICER’S REVIEW
NEW BUSINESS PERFORMANCE
VONB, ANP and Margin by Segment
2020 2019 VONB Change
VONB VONB YoY YoY
US$ millions, unless otherwise stated VONB Margin ANP VONB Margin ANP CER AER
Hong Kong 550 44.7% 1,138 1,621 66.1% 2,393 (66)% (66)%
Thailand 469 71.0% 661 494 67.7% 729 (4)% (5)%
Singapore 330 63.4% 520 352 65.5% 538 (5)% (6)%
Malaysia 222 59.9% 369 258 63.1% 406 (13)% (14)%
Mainland China 968 80.9% 1,197 1,167 93.5% 1,248 (17)% (17)%
Other Markets 514 38.4% 1,334 535 41.9% 1,271 (4)% (4)%
Subtotal 3,053 57.7% 5,219 4,427 66.6% 6,585 (31)% (31)%
Adjustment to reflect
consolidated reserving and
capital requirements (103) n/m n/m (87) n/m n/m n/m n/m
After-tax value of unallocated
Group Office expenses (161) n/m n/m (154) n/m n/m n/m n/m
Total before
non-controlling interests 2,789 52.6% 5,219 4,186 62.9% 6,585 (33)% (33)%
Non-controlling interests (24) n/m n/m (32) n/m n/m n/m n/m
Total 2,765 52.6% 5,219 4,154 62.9% 6,585 (33)% (33)%
While VONB of US$2,765 million in 2020 was lower by 33 per cent compared to 2019, our rapid adoption of
new digital tools and the general easing of movement restrictions supported a recovery in sales momentum.
AIA China became the largest contributor to the Group’s VONB in 2020 and was the first of our reportable
segments to show a recovery in sales momentum as the country emerged from the strict lockdowns in March
2020. VONB for the rest of the Group, excluding sales to Mainland Chinese visitors which remained minimal,
recovered strongly in the second half with an increase of 23...
```
