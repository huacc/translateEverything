# Prompt B Batch 20 Comparison

- model: `claude-opus-4-6`
- paragraph_count: `20`
- parsed_paragraph_count: `20`
- avg_token_f1: `0.658`
- avg_sequence_ratio: `0.3989`

## System Prompt

```text
1. 核心角色 (Role)
你是一位拥有20年国际保险集团（如 AIA、Prudential）年报编写经验的资深翻译官。你不仅精通翻译，更深刻理解投资者关系（Investor Relations）的修辞艺术，擅长将中文的叙述转化为具有 CEO 高度和金融严谨度的英文文本。

2. 翻译核心准则 (Core Principles)

A. 术语生命周期管理 (Terminology Lifecycle)
首现原则：所有核心财务指标在当前段落首次出现时必须使用全称并括号标注缩写，例如：value of new business (VONB)，operating profit after tax (OPAT)。
后续原则：同一段落后续提及该指标时，直接使用缩写。
精准对照：
- 内涵價值權益 -> EV Equity
- 當地資本總和法 -> Local Capital Summation Method (LCSM)
- 產生的基本自由盈餘 -> underlying free surplus generation (UFSG)
- 有效保單組合 -> in-force portfolio

B. 品牌与机构表达 (Branding & Institutional Style)
专有名词处理：公司的目标（Purpose）必须视作专有名词。
帮助大众活出健康、长久、好生活 必须准确译为 "helping people live Healthier, Longer, Better Lives"。
当提到董事会时，使用 the Board 或 the board of Directors (Board)。

C. 财务与地区表达 (Financial & Regional Conventions)
按年译为 year-on-year，去年同期译为 prior year。
中國內地 -> Mainland China。
香港 -> Hong Kong 或 Hong Kong SAR。
區內 -> in the region。
金额格式保持为 US$X,XXX million / US$X.X billion 这一类国际年报格式。
如果原文是每股 100.30 港仙、135.30 港仙 这类表达，必须译为 100.30 Hong Kong cents per share、135.30 Hong Kong cents per share，不得擅自换算成 HK$1.003 或 HK$1.353。
百分比统一使用 per cent，不使用 %。
采用 British / International English（例如：capitalisation, programme, honour, recognised）。

D. 句法重构 (Syntactic Re-engineering)
严禁逐句硬对齐，但也不得为了华丽而过度改写。
如果中文由多个短句共同构成一个完整观点，可重组为更自然、更连贯的英文年报句式。
优先使用符合年报文体的介词短语、分词结构和后置修饰，但必须保持原文事实边界、语气和逻辑顺序。

E. 词汇与语气 (Tone & Lexicon)
优先使用正式、稳健、可出版的年报用语。
体现 / 反映 可译为 underpinned by、reflecting、synonymous with，但必须根据上下文克制使用。
领导 / 管理 在合适语境下可提升为 stewardship，但不要机械套用。
利用机遇 可译为 capture the enormous opportunities 或 capture the significant opportunities，按语境选择。
允许使用 immensely、steadfast、unprecedented、robust、unparalleled 等词，但不得堆砌。

3. 负面约束 (Negative Constraints)
禁止使用中式英语思维（如：The value is... because of...）。
禁止直译四字成语，必须转化为符合英文商业语境的功能性表达。
禁止主谓宾简单句机械堆砌。
禁止为追求文采而改动数字、单位、比较关系、主体责任归属。
财务报表标题和页码索引（如 ### S01 | page 10）必须保持原样，不翻译，不改写。

4. 执行指令 (Execution Task)
请翻译以下内容。
在翻译时请先静默识别：
- 当前段落中的关键财务指标及其升降趋势；
- 公司使命、机构名称、人名、地名等需要合规处理的词汇。

输出要求：
先输出翻译结果。
在全部翻译结果之后，再简要说明你在重构叙事方面做出的两处关键改进。
除译文和上述两处说明外，不输出其他分析过程。

```

## User Prompt

```text
现在请直接翻译以下20个中文年报正文段落。

输出要求：
1. 必须逐段翻译，不合并，不拆分，不省略。
2. 保持编号顺序。
3. 每段必须按原编号输出。
4. 输出格式必须严格如下：
### S01
<英文译文>

### S02
<英文译文>

其余段落依此类推，直到 ### S20。

5. 在全部译文之后，单独追加：
### Narrative Notes
<两处关键改进的简要说明>

待翻译段落：

### S01 | page 10
友邦保險在亞洲歷史悠久，源遠流長，經歷各種社會動盪和不明朗時期仍能妥善管理業務，因而贏得卓著的聲譽，體現友邦保險誠可信賴、強韌穩健，並堅持為持分者做對的事。自2020年初以來，2019冠狀病毒病大流行導致營商環境不斷變化及日趨複雜，而政治、宏觀經濟及資本市場亦出現前所未見的轉移。在這樣的環境下，友邦保險的財務實力，以及「幫助大眾活出健康、長久、好生活」的目標，更具重大意義。本人衷心感謝友邦保險所有員工、代理和合作夥伴，即使面對最嚴峻的挑戰，他們仍關懷社區，克盡己職，專心致志地為客戶、其家庭以及我們的社區提供支援。

### S02 | page 10
由於2019冠狀病毒病相關的控制措施對新業務銷售造成影響，新業務價值下降至27.65億美元。我們迅速採用嶄新的數碼工具，提升業務運作效率，加上近期放寬外出限制，帶動銷售動力強勁復蘇，並延續至2021年初。與去年同期比較，2021年首兩個月的新業務價值增長15%。

### S03 | page 10
稅後營運溢利增長5%至59.42億美元，產生的基本自由盈餘則上升7%至58.43億美元，反映我們擁有高質素的經常性盈利來源。內涵價值權益創新高，達672億美元。截至2020年12月31日，集團當地資本總和法覆蓋率為374%，足證我們雄厚的資本實力和嚴謹的財務管理。

### S04 | page 10
董事會建議派發末期股息每股100.30港仙，增加7.5%，反映我們的財務業績穩健強韌，同時董事會持續對本集團未來前景充滿信心。這使2020年的全年股息達到每股135.30港仙。董事會秉承友邦保險行之已久的審慎、可持續及漸進的派息政策，讓本集團可把握未來的增長機遇，並保持財務靈活性。

### S05 | page 11
在2020年第四季，我們慶祝友邦保險在香港聯交所上市10週年。回顧當年友邦保險的上市刷新多項紀錄，至今仍是全球保險業界規模最大的首次公開招股。能夠與董事會成員並肩合作，本人深感榮幸和欣慰。友邦保險的業務在此期間繼往開來，不斷擴展，成為以市值計全球最大的人壽保險公司。

### S06 | page 11
董事會的所有非執行董事均由獨立人士出任，他們在公營和私營產業擁有廣泛的管治和領導經驗。我們同心協力，銳意維持奉行最高國際企業管治標準的公司文化。我們深信根深蒂固的企業管治文化，加上穩健的風險管理架構，是每家機構可持續發展的基礎。

### S07 | page 11
董事會的重要責任之一是確保領導層人才輩出，並執行有效的繼任安排。我們歡迎李源祥先生於2020年6月1日接替榮休的黃經輝先生，擔任集團首席執行官兼總裁。本人謹代表董事會向李源祥先生及其管理層團隊深表謝意，他們在這段前所未見的環境發揮優秀的管理才能，帶領我們的業務向前邁進。我們也衷心感謝黃經輝先生多年來的卓越領導及對友邦保險所作出的重大貢獻。

### S08 | page 11
環境、社會及管治議題對全球的影響日形重要。我們當竭盡所能，協助推動社會邁向更美好的未來，而我們的環境、社會及管治措施在2020年再度備受肯定。根據評級機構Sustainalytics的評選，友邦保險在超過270家保險公司中排名第二，足證我們卓越的企業管治實力和質素。此外，我們繼續榮獲Institutional Shareholder ServicesInc.(ISS)頒發「Prime」環境、社會及管治企業評級(ESG Corporate Rating)，認同我們為業界可持續發展表現最佳的公司之一。我們相信我們在這方面仍需採取更多措施，為社區實現更美好的成果。這仍是我個人與董事會成員、高級管理層團隊以及全體員工共同秉持的優先指標。

### S09 | page 11
今天，客戶對友邦保險產品、服務及高質素建議日益增長的需求從未如此殷切。我們的策略建基於亞洲強勁的結構性增長動力，並獲多項因素支持，包括前所未見的財富創造、保障缺口迅速擴大、消費者取向持續轉變、數碼技術普及，以及市場聚焦於長遠的可持續發展。董事會充滿信心，友邦保險具備優越條件，把握區內展現的龐大機遇，在客戶及其家庭最需要的時刻提供財務保障，使其安心無憂，並同時為所有持分者創造共享價值。

### S10 | page 11
最後，全賴客戶及股東的信任，友邦保險才能自上市以來表現強勁和持續增長。本人謹代表董事會全體成員，衷心感謝您們一直以來的支持。

### S11 | page 13
友邦保險是客戶誠可信賴的夥伴，讓客戶在關注財務安全和家庭保障時仍可安心無憂。儘管2019冠狀病毒病大流行的影響深遠，但我衷心感謝我們的員工、代理和合作夥伴在適應新工作方式並確保為客戶提供無間斷的支援時，展現靈活應變的能力和克盡己職的精神。

### S12 | page 13
自疫情大流行開始以來，本集團的各業務團隊反應迅速，積極協助紓緩對社區的影響，同時確保員工安全。本集團為此廣泛採取多項措拖，包括財政支持、提供醫療物資、免費保障覆蓋、獲取醫療保健資源、精簡服務流程和加快理賠支付，令我引以為榮。我們一如既往找出每一個可以作出理賠的理由，年內已支付逾160億美元的保險給付及理賠，為客戶提供極其重要的財務保障。

### S13 | page 13
儘管為遏制2019冠狀病毒病傳播的措施導致新業務價值減少至27.65億美元，但隨著外出限制放寬，銷售動力轉趨正面，並在2021年展開非常強勁的勢頭，首兩個月的新業務價值按年增長15%。我們規模龐大和持續增長的有效保單組合所帶來的高質素和經常性收入來源，帶動2020年稅後營運溢利增加5%，期內產生的基本自由盈餘則增長7%。截至2020年12月31日，內涵價值權益創新高，達672億美元，集團當地資本總和法覆蓋率為374%，足證我們雄厚的資本實力和嚴謹的財務管理。

### S14 | page 13
董事會建議2020年末期股息增加7.5%至每股100.30港仙。這秉承友邦保險行之已久的審慎、可持續及漸進的派息政策，讓本集團可把握未來的增長機遇，並且保持財務靈活性。

### S15 | page 13
友邦保險具有多項顯著優勢，讓我們在競爭激烈的市場別樹一幟。我們在亞洲經營數十載，擁有區內無可比擬的平台，並於我們業務所在的大部分市場雄踞領導地位。我們始終如一地百分百專注於亞洲市場，有助我們在全球最具吸引力的壽險業地區全面把握增長機遇。這份專注結合我們領導團隊在亞洲的豐富經驗及員工的優秀質素，一直是我們表現卓越的重要動力。

### S16 | page 13
我們無可比擬的分銷實力能直接接觸客戶，並提供高質素的專業建議，協助滿足亞洲消費者龐大且日益增長的長期保障和儲蓄需求。如今大眾比以往更期望企業能以符合長遠可持續發展的方式應對他們的需要。友邦保險擁有市場領先的品牌，以幫助大眾實踐健康、長久、好生活的目標為基礎。

### S17 | page 13
我們旨在使友邦保險在科技應用方面領先全球，加強互聯互通，擴大規模和提升效率。更深入瞭解數據分析有助我們締造獨特和個人化的客戶體驗。切合和反映個人需求和生活方式的產品及服務，改變了大眾對人壽保險的看法，為我們與客戶建立長遠關係奠定堅實的基礎。

### S18 | page 13
儘管2020年是前所未見的一年，但我對亞洲壽險行業的前景和友邦保險的未來比以往更為樂觀。我們繼續挑戰自己，發展我們的優先任務，以確保我們能繼續適切地迎合客戶期望和財務需求的轉變。我們的全新企業策略建基於友邦保險的現有實力，推進轉型過程，以在未來為客戶提供最佳的服務。

### S19 | page 14
友邦保險中國業務在2020年為本集團新業務價值帶來最大貢獻，並在2021年初表現卓越，與2020年同期比較，今年首兩個月錄得非常強勁的新業務價值增長。儘管2020年的9.68億美元新業務價值較2019年下降17%，但這主要由於2019冠狀病毒病在首季爆發初期新銷售有限所致。年內稅後營運溢利增長14%，主要是由於我們日益增長的有效保單組合及有利的理賠經驗。

### S20 | page 14
在2020年，我們成功獲得監管機搆批復，將上海分公司改建為中國內地首家外資獨資人身保險子公司。於2021年3月，我們已獲得中國銀行保險監督委員會批復，准予在四川省開業。四川省是中國內地以國內生產總值計的第六大省份，以人口計為第四大省，為友邦保險帶來重大的長期增長機遇。
```

## Claude Raw Response

```text
### S01
AIA has earned a distinguished reputation across Asia through its long and storied history of successfully navigating periods of social upheaval and uncertainty, underpinned by our trusted, resilient character and steadfast commitment to doing the right thing for our stakeholders. Since early 2020, the COVID-19 pandemic has created an ever-changing and increasingly complex operating environment, accompanied by unprecedented shifts in the political, macroeconomic and capital market landscape. Against this backdrop, AIA's financial strength and our Purpose of helping people live Healthier, Longer, Better Lives have never been more significant. I am immensely grateful to all of our employees, agents and partners who, even in the face of the most severe challenges, have remained dedicated to caring for our communities and supporting our customers, their families and the communities we serve.

### S02
Value of new business (VONB) declined to US$2,765 million as new business sales were impacted by COVID-19-related control measures. We rapidly adopted innovative digital tools to enhance operational efficiency, and the recent easing of mobility restrictions has driven a robust recovery in sales momentum that has continued into early 2021. VONB for the first two months of 2021 increased 15 per cent compared with the prior year.

### S03
Operating profit after tax (OPAT) grew 5 per cent to US$5,942 million, while underlying free surplus generation (UFSG) rose 7 per cent to US$5,843 million, reflecting our high-quality recurring earnings streams. EV Equity reached a record US$67.2 billion. As at 31 December 2020, the Group's Local Capital Summation Method (LCSM) coverage ratio stood at 374 per cent, demonstrating our robust capital strength and rigorous financial stewardship.

### S04
The Board has proposed a final dividend of 100.30 Hong Kong cents per share, an increase of 7.5 per cent, reflecting our resilient financial performance and the Board's continued confidence in the Group's future prospects. This brings the full-year dividend for 2020 to 135.30 Hong Kong cents per share. The Board remains committed to AIA's long-standing prudent, sustainable and progressive dividend policy, which enables the Group to capture future growth opportunities while maintaining financial flexibility.

### S05
In the fourth quarter of 2020, we celebrated the tenth anniversary of AIA's listing on the Hong Kong Stock Exchange. AIA's listing set multiple records at the time and remains the largest initial public offering in the global insurance industry to date. I am honoured and privileged to have worked alongside the members of the Board as AIA's business has continued to expand during this period, establishing the Company as the largest life insurer in the world by market capitalisation.

### S06
All of the Board's non-executive directors are independent and bring extensive governance and leadership experience from both the public and private sectors. Together, we are committed to maintaining a corporate culture that upholds the highest international standards of corporate governance. We firmly believe that a deeply embedded governance culture, combined with a robust risk management framework, forms the foundation for the sustainable development of any institution.

### S07
One of the Board's key responsibilities is to ensure a strong pipeline of leadership talent and effective succession arrangements. We welcomed Mr Lee Yuan Siong, who succeeded the retiring Mr Ng Keng Hooi as Group Chief Executive and President on 1 June 2020. On behalf of the Board, I extend my sincere gratitude to Mr Lee and his management team for their outstanding stewardship in navigating our business through this unprecedented environment. We also express our heartfelt thanks to Mr Ng for his exceptional leadership and significant contributions to AIA over many years.

### S08
Environmental, social and governance (ESG) issues are assuming ever-greater importance globally. We are committed to doing everything we can to help drive society towards a better future, and our ESG initiatives received further recognition in 2020. AIA was ranked second among more than 270 insurance companies by Sustainalytics, demonstrating the excellence and quality of our corporate governance capabilities. In addition, we continued to receive a "Prime" ESG Corporate Rating from Institutional Shareholder Services Inc. (ISS), recognising us as one of the industry's best performers in sustainability. We believe there is still much more we must do to deliver better outcomes for our communities. This remains a personal priority for me, the Board, the senior management team and all of our employees.

### S09
Today, customer demand for AIA's products, services and high-quality advice has never been more compelling. Our strategy is built upon Asia's powerful structural growth drivers and is supported by multiple factors, including unprecedented wealth creation, a rapidly widening protection gap, evolving consumer preferences, the proliferation of digital technology and a market focus on long-term sustainability. The Board is confident that AIA is exceptionally well positioned to capture the enormous opportunities emerging across the region, providing financial protection and peace of mind to customers and their families when they need it most, while creating shared value for all stakeholders.

### S10
Finally, it is the trust of our customers and shareholders that has enabled AIA's strong and sustained growth since our listing. On behalf of all members of the Board, I extend my sincere thanks for your continued support.

### S11
AIA is a trusted partner to our customers, providing them with peace of mind as they focus on their financial security and family protection. Despite the far-reaching impact of the COVID-19 pandemic, I am deeply grateful to our employees, agents and partners for demonstrating remarkable adaptability and dedication in adjusting to new ways of working while ensuring uninterrupted support for our customers.

### S12
Since the onset of the pandemic, our business teams across the Group have responded swiftly and proactively to help mitigate the impact on our communities while ensuring the safety of our employees. I am proud of the extensive range of measures we have implemented, including financial support, provision of medical supplies, complimentary coverage, access to healthcare resources, streamlined service processes and accelerated claims payments. True to our commitment to finding every reason to pay, we paid over US$16 billion in insurance benefits and claims during the year, providing critically important financial protection to our customers.

### S13
Although measures to contain the spread of COVID-19 resulted in VONB declining to US$2,765 million, sales momentum turned positive as mobility restrictions eased and has commenced 2021 with very strong momentum, with VONB for the first two months growing 15 per cent year-on-year. The high-quality recurring income streams generated by our large and growing in-force portfolio drove a 5 per cent increase in OPAT for 2020, while UFSG for the period grew 7 per cent. As at 31 December 2020, EV Equity reached a record US$67.2 billion and the Group's LCSM coverage ratio stood at 374 per cent, demonstrating our robust capital strength and rigorous financial stewardship.

### S14
The Board has proposed a 7.5 per cent increase in the 2020 final dividend to 100.30 Hong Kong cents per share. This is consistent with AIA's long-standing prudent, sustainable and progressive dividend policy, which enables the Group to capture future growth opportunities while maintaining financial flexibility.

### S15
AIA possesses multiple distinctive advantages that set us apart in a competitive marketplace. Our decades of operating experience in Asia have created an unparalleled platform across the region, with leadership positions in most of the markets where we operate. Our unwavering 100 per cent focus on Asia enables us to fully capture growth opportunities in the world's most attractive life insurance region. This focus, combined with our leadership team's deep experience in Asia and the outstanding quality of our people, has been a vital driver of our exceptional performance.

### S16
Our unparalleled distribution strength provides direct customer access and high-quality professional advice, helping to meet the substantial and growing long-term protection and savings needs of Asian consumers. Today, people expect more than ever that companies will address their needs in a manner consistent with long-term sustainability. AIA has a market-leading brand built upon our Purpose of helping people live Healthier, Longer, Better Lives.

### S17
We aim to position AIA as a global leader in technology adoption, enhancing connectivity, expanding scale and improving efficiency. Deeper insights from data analytics enable us to create distinctive and personalised customer experiences. Products and services that are relevant to and reflect individual needs and lifestyles are transforming perceptions of life insurance, establishing a solid foundation for building enduring relationships with our customers.

### S18
Although 2020 was an unprecedented year, I am more optimistic than ever about the prospects for Asia's life insurance industry and AIA's future. We continue to challenge ourselves and evolve our priorities to ensure we remain responsive to changing customer expectations and financial needs. Our new corporate strategy builds upon AIA's existing strengths and advances our transformation journey to deliver the best possible service to our customers in the years ahead.

### S19
AIA China delivered the largest contribution to the Group's VONB in 2020 and has performed exceptionally well in early 2021, recording very strong VONB growth in the first two months of the year compared with the prior year. Although VONB of US$968 million for 2020 declined 17 per cent from 2019, this was primarily due to limited new sales in the first quarter during the initial outbreak of COVID-19. OPAT for the year increased 14 per cent, driven mainly by our growing in-force portfolio and favourable claims experience.

### S20
In 2020, we successfully obtained regulatory approval to convert our Shanghai Branch into Mainland China's first wholly foreign-owned life insurance subsidiary. In March 2021, we received approval from the China Banking and Insurance Regulatory Commission to commence operations in Sichuan Province. Sichuan is Mainland China's sixth-largest province by gross domestic product and fourth-largest by population, presenting significant long-term growth opportunities for AIA.

---

### Narrative Notes

**Key Improvement 1: Institutional Voice and Temporal Precision**  
Throughout the translation, I systematically replaced generic temporal expressions with year-report-appropriate constructions. For instance, "去年同期" became "prior year" rather than "same period last year," and "按年" was rendered as "year-on-year" in financial contexts but "compared with the prior year" in narrative contexts. This ensures consistency with international annual report conventions and elevates the institutional tone expected by global investors.

**Key Improvement 2: Strategic Recasting of Purpose and Brand Language**  
I treated AIA's Purpose statement as a proprietary brand asset, consistently rendering "幫助大眾活出健康、長久、好生活" as "helping people live Healthier, Longer, Better Lives" with capitalisation to signal its status as a defined corporate mission. Similarly, I restructured phrases like "體現友邦保險誠可信賴、強韌穩健" into "underpinned by our trusted, resilient character," transforming a descriptive clause into a more dynamic participial construction that better reflects CEO-level strategic narrative while preserving factual accuracy.
```

## Claude Tail Notes

```text
### Narrative Notes
**Key Improvement 1: Institutional Voice and Temporal Precision**  
Throughout the translation, I systematically replaced generic temporal expressions with year-report-appropriate constructions. For instance, "去年同期" became "prior year" rather than "same period last year," and "按年" was rendered as "year-on-year" in financial contexts but "compared with the prior year" in narrative contexts. This ensures consistency with international annual report conventions and elevates the institutional tone expected by global investors.

**Key Improvement 2: Strategic Recasting of Purpose and Brand Language**  
I treated AIA's Purpose statement as a proprietary brand asset, consistently rendering "幫助大眾活出健康、長久、好生活" as "helping people live Healthier, Longer, Better Lives" with capitalisation to signal its status as a defined corporate mission. Similarly, I restructured phrases like "體現友邦保險誠可信賴、強韌穩健" into "underpinned by our trusted, resilient character," transforming a descriptive clause into a more dynamic participial construction that better reflects CEO-level strategic narrative while preserving factual accuracy.
```

## Human Reference Combined

### S01
Throughout AIA’s long history in the region we have managed our businesses through many periods of change and uncertainty, earning our company a reputation which is synonymous with trust, resilience and doing the right thing for our stakeholders. From early 2020, the COVID-19 pandemic presented an ever-changing and complex operating environment and we witnessed unprecedented shifts in politics, macroeconomics and capital markets. AIA’s financial strength and Purpose of “helping people live Healthier, Longer, Better Lives” has never been more relevant. I am immensely grateful to all of our employees, agents and partners for their care and dedication, remaining steadfast in supporting our customers, their families, and our communities, through this most challenging time.

### S02
New business sales were affected by COVID-19 related containment measures, with value of new business (VONB) reducing to US$2,765 million. Our rapid adoption of new digital tools helped maintain business activity and, together with more recent easing of movement restrictions, led to a robust recovery in sales momentum, which has continued into the beginning of 2021. VONB for the first two months of 2021 grew by 15 per cent compared with the same period in the prior year.

### S03
Operating profit after tax (OPAT) increased by 5 per cent to US$5,942 million and underlying free surplus generation (UFSG) grew by 7 per cent to US$5,843 million, reflecting our high-quality, recurring sources of earnings. EV Equity reached a new high of US$67.2 billion. The Group Local Capital Summation Method (LCSM) cover ratio was 374 per cent as at 31 December 2020, demonstrating our resilient capital position and disciplined financial management.

### S04
The board of Directors (Board) has recommended a final dividend of 100.30 Hong Kong cents per share, which is an increase of 7.5 per cent, reflecting the strength and resilience of our financial results and the Board’s continued confidence in the future prospects of the Group. This brings the total dividend for 2020 to 135.30 Hong Kong cents per share. The Board follows AIA’s established prudent, sustainable and progressive dividend policy, allowing for future growth opportunities and the financial flexibility of the Group.

### S05
In the fourth quarter of 2020, we celebrated the 10th anniversary of AIA’s historic listing on the Hong Kong Stock Exchange. AIA’s market debut established new records at the time and remains the largest-ever initial public offering in the global insurance sector. It has been my honour and pleasure to work alongside our Board members as our business has gone from strength to strength over this time to become the largest life insurance company in the world by market capitalisation.

### S06
All of the Board’s non-executive directors are independent and have extensive governance and leadership experience in the public and private sectors. Together, we are committed to maintaining a culture that upholds the highest international standards of corporate governance. We are firm believers that a strong governance culture, supported by a sound risk management framework, is fundamental to the sustainability of every organisation.

### S07
An important responsibility for the Board is to ensure a robust leadership pipeline and effective succession planning. We welcomed Lee Yuan Siong as Group Chief Executive and President on 1 June 2020, following the retirement of Ng Keng Hooi. On behalf of the Board, I would like to thank Yuan Siong and his senior management AND team for their outstanding stewardship of our businesses in these extraordinary times. We are also very grateful to Keng Hooi for his valuable leadership and substantial contributions to AIA over many years.

### S08
The global impacts of Environmental, Social and Governance (ESG) issues continue to be of great significance. We remain committed to playing our part in the transition to a brighter future and our ESG efforts have been recognised again in 2020. The rating agency, Sustainalytics, ranked AIA second in our industry out of more than 270 peers, noting the strength and quality of our corporate governance. Additionally, our ESG Corporate Rating score from Institutional Shareholder Services Inc. (ISS) remains “Prime”, placing us among the best in our industry for our sustainability performance. AIA recognises that there is much more we can do in this area to achieve better outcomes for our communities and it remains a personal priority that I share with my Board colleagues, our senior management team and all our employees.

### S09
The growing need for AIA’s products, services and high-quality advice has never been more evident than it is today. Our strategy builds on the powerful structural drivers of growth prevalent in Asia, underpinned by unprecedented wealth creation, a rapidly expanding protection gap, evolving consumer preferences, the rise of digital technology and a focus on long-term sustainability. The Board remains confident that AIA is extremely well positioned to capture the enormous opportunities available in the region by providing our customers and their families with financial peace of mind at a time when they need it the most, while creating shared value for all our stakeholders.

### S10
Finally, AIA’s strong performance and growth since our initial public offering would not have been possible without the trust of our customers and shareholders. On behalf of the entire Board, I am deeply grateful for your enduring support.

### S11
AIA is a trusted partner to our customers, providing peace of mind when they are concerned about the financial security and well-being of their families. While the impacts of the COVID-19 pandemic have been far-reaching, my deepest gratitude goes to our employees, agents and partners for their tremendous agility and dedication as they adapted to new working practices and ensured uninterrupted customer support.

### S12
Since the onset of the pandemic, our businesses have responded quickly and proactively to help alleviate the impact on our communities, while ensuring the safety of our people. I am immensely proud of the wide-ranging initiatives undertaken including financial support, provision of medical supplies, free protection cover, access to health resources, streamlined services and expedited claim payments. We always look for every reason to pay a claim and, over the year, we paid more than US$16 billion in benefits and claims, providing vital financial protection for our customers.

### S13
While value of new business (VONB) was affected by COVID-19 containment measures, reducing to US$2,765 million, we delivered positive sales momentum as movement restrictions eased and made a very strong start AND to 2021 with 15 per cent year-on-year VONB growth in the first two months. Our large and growing in-force portfolio with high-quality, recurring sources of earnings delivered a 5 per cent increase in operating profit after tax (OPAT) in 2020 and a 7 per cent increase in underlying free surplus generation (UFSG). EV Equity reached a new high of US$67.2 billion and the Group LCSM cover ratio was 374 per cent as at 31 December 2020, demonstrating our robust capital position and disciplined financial management.

### S14
The board of Directors (Board) has recommended a 7.5 per cent increase in the final dividend for 2020 to 100.30 Hong Kong cents per share. This follows AIA’s established prudent, sustainable and progressive dividend policy, allowing for future growth opportunities and the financial flexibility of the Group.

### S15
AIA has many significant advantages that differentiate us from our competitors. We have an unparalleled platform in Asia built up over many decades and hold leading positions in the majority of our markets. Our 100 per cent focus on Asia will not change and enables us to capture the full growth opportunities available in the world’s most attractive region for life insurance. This focus, combined with the extensive experience of our leadership team in Asia and the quality of our people, has been an important driver of our success.

### S16
Our unrivalled distribution provides direct access to customers, delivering high-quality professional advice to help address the significant and growing long-term protection and savings needs of consumers in Asia. Now more than ever, people expect companies to respond in a way that is aligned with long-term sustainability. AIA has a market-leading brand that is underpinned by our Purpose of helping people live Healthier, Longer, Better Lives.

### S17
Our aim is to position AIA as a global leader in the use of technology, embracing greater connectivity, scale and efficiency. Deeper insights from data analytics enable distinctive and personalised customer experiences. Products and services that are relevant and reflect an individual’s needs and lifestyle change the way life insurance is perceived and provide a strong basis for developing long-term relationships with our customers.

### S18
While 2020 was an unprecedented year, it has made me more optimistic than ever about the prospects for the life insurance industry in Asia and the future of AIA. We continue to challenge ourselves and develop our priorities to ensure that we remain highly relevant to our customers as their expectations and financial needs evolve. Our new corporate strategy builds on AIA’s existing strengths and enables the transformation that we will make to best serve our customers well into the future.

### S19
AIA China became the largest contributor to the Group’s VONB in 2020 and delivered a successful start to 2021 with very strong VONB growth in the first two months of the year compared with the same period in 2020. While VONB of US$968 million for 2020 was 17 per cent lower than 2019, this was mostly due to limited new sales during the initial outbreak of COVID-19 in the first quarter. OPAT increased by 14 per cent for the year, primarily driven by growth in our in-force portfolio and favourable claims experience.

### S20
In 2020, we successfully obtained regulatory approval and completed the conversion of our Shanghai branch to become the first wholly foreign owned life insurance subsidiary in Mainland China. In March 2021, we received approval from the China Banking and Insurance Regulatory Commission (CBIRC) to begin operations in Sichuan. Sichuan is the sixth largest province by GDP in Mainland China and the fourth largest by population, representing a significant long-term growth opportunity for AIA.

## Per Paragraph Comparison

### S01 | page 10

- unit_ids: `p10_g01, p10_b18`
- token_f1: `0.6449`
- sequence_ratio: `0.3931`

#### Source ZH

```text
友邦保險在亞洲歷史悠久，源遠流長，經歷各種社會動盪和不明朗時期仍能妥善管理業務，因而贏得卓著的聲譽，體現友邦保險誠可信賴、強韌穩健，並堅持為持分者做對的事。自2020年初以來，2019冠狀病毒病大流行導致營商環境不斷變化及日趨複雜，而政治、宏觀經濟及資本市場亦出現前所未見的轉移。在這樣的環境下，友邦保險的財務實力，以及「幫助大眾活出健康、長久、好生活」的目標，更具重大意義。本人衷心感謝友邦保險所有員工、代理和合作夥伴，即使面對最嚴峻的挑戰，他們仍關懷社區，克盡己職，專心致志地為客戶、其家庭以及我們的社區提供支援。
```

#### Claude

```text
AIA has earned a distinguished reputation across Asia through its long and storied history of successfully navigating periods of social upheaval and uncertainty, underpinned by our trusted, resilient character and steadfast commitment to doing the right thing for our stakeholders. Since early 2020, the COVID-19 pandemic has created an ever-changing and increasingly complex operating environment, accompanied by unprecedented shifts in the political, macroeconomic and capital market landscape. Against this backdrop, AIA's financial strength and our Purpose of helping people live Healthier, Longer, Better Lives have never been more significant. I am immensely grateful to all of our employees, agents and partners who, even in the face of the most severe challenges, have remained dedicated to caring for our communities and supporting our customers, their families and the communities we serve.
```

#### Human Reference

```text
Throughout AIA’s long history in the region we have managed our businesses through many periods of change and uncertainty, earning our company a reputation which is synonymous with trust, resilience and doing the right thing for our stakeholders. From early 2020, the COVID-19 pandemic presented an ever-changing and complex operating environment and we witnessed unprecedented shifts in politics, macroeconomics and capital markets. AIA’s financial strength and Purpose of “helping people live Healthier, Longer, Better Lives” has never been more relevant. I am immensely grateful to all of our employees, agents and partners for their care and dedication, remaining steadfast in supporting our customers, their families, and our communities, through this most challenging time.
```

### S02 | page 10

- unit_ids: `p10_g02, p10_b21`
- token_f1: `0.6069`
- sequence_ratio: `0.2961`

#### Source ZH

```text
由於2019冠狀病毒病相關的控制措施對新業務銷售造成影響，新業務價值下降至27.65億美元。我們迅速採用嶄新的數碼工具，提升業務運作效率，加上近期放寬外出限制，帶動銷售動力強勁復蘇，並延續至2021年初。與去年同期比較，2021年首兩個月的新業務價值增長15%。
```

#### Claude

```text
Value of new business (VONB) declined to US$2,765 million as new business sales were impacted by COVID-19-related control measures. We rapidly adopted innovative digital tools to enhance operational efficiency, and the recent easing of mobility restrictions has driven a robust recovery in sales momentum that has continued into early 2021. VONB for the first two months of 2021 increased 15 per cent compared with the prior year.
```

#### Human Reference

```text
New business sales were affected by COVID-19 related containment measures, with value of new business (VONB) reducing to US$2,765 million. Our rapid adoption of new digital tools helped maintain business activity and, together with more recent easing of movement restrictions, led to a robust recovery in sales momentum, which has continued into the beginning of 2021. VONB for the first two months of 2021 grew by 15 per cent compared with the same period in the prior year.
```

### S03 | page 10

- unit_ids: `p10_g03`
- token_f1: `0.7353`
- sequence_ratio: `0.5416`

#### Source ZH

```text
稅後營運溢利增長5%至59.42億美元，產生的基本自由盈餘則上升7%至58.43億美元，反映我們擁有高質素的經常性盈利來源。內涵價值權益創新高，達672億美元。截至2020年12月31日，集團當地資本總和法覆蓋率為374%，足證我們雄厚的資本實力和嚴謹的財務管理。
```

#### Claude

```text
Operating profit after tax (OPAT) grew 5 per cent to US$5,942 million, while underlying free surplus generation (UFSG) rose 7 per cent to US$5,843 million, reflecting our high-quality recurring earnings streams. EV Equity reached a record US$67.2 billion. As at 31 December 2020, the Group's Local Capital Summation Method (LCSM) coverage ratio stood at 374 per cent, demonstrating our robust capital strength and rigorous financial stewardship.
```

#### Human Reference

```text
Operating profit after tax (OPAT) increased by 5 per cent to US$5,942 million and underlying free surplus generation (UFSG) grew by 7 per cent to US$5,843 million, reflecting our high-quality, recurring sources of earnings. EV Equity reached a new high of US$67.2 billion. The Group Local Capital Summation Method (LCSM) cover ratio was 374 per cent as at 31 December 2020, demonstrating our resilient capital position and disciplined financial management.
```

### S04 | page 10

- unit_ids: `p10_g04, p10_b27`
- token_f1: `0.7`
- sequence_ratio: `0.6263`

#### Source ZH

```text
董事會建議派發末期股息每股100.30港仙，增加7.5%，反映我們的財務業績穩健強韌，同時董事會持續對本集團未來前景充滿信心。這使2020年的全年股息達到每股135.30港仙。董事會秉承友邦保險行之已久的審慎、可持續及漸進的派息政策，讓本集團可把握未來的增長機遇，並保持財務靈活性。
```

#### Claude

```text
The Board has proposed a final dividend of 100.30 Hong Kong cents per share, an increase of 7.5 per cent, reflecting our resilient financial performance and the Board's continued confidence in the Group's future prospects. This brings the full-year dividend for 2020 to 135.30 Hong Kong cents per share. The Board remains committed to AIA's long-standing prudent, sustainable and progressive dividend policy, which enables the Group to capture future growth opportunities while maintaining financial flexibility.
```

#### Human Reference

```text
The board of Directors (Board) has recommended a final dividend of 100.30 Hong Kong cents per share, which is an increase of 7.5 per cent, reflecting the strength and resilience of our financial results and the Board’s continued confidence in the future prospects of the Group. This brings the total dividend for 2020 to 135.30 Hong Kong cents per share. The Board follows AIA’s established prudent, sustainable and progressive dividend policy, allowing for future growth opportunities and the financial flexibility of the Group.
```

### S05 | page 11

- unit_ids: `p11_g01`
- token_f1: `0.6543`
- sequence_ratio: `0.2472`

#### Source ZH

```text
在2020年第四季，我們慶祝友邦保險在香港聯交所上市10週年。回顧當年友邦保險的上市刷新多項紀錄，至今仍是全球保險業界規模最大的首次公開招股。能夠與董事會成員並肩合作，本人深感榮幸和欣慰。友邦保險的業務在此期間繼往開來，不斷擴展，成為以市值計全球最大的人壽保險公司。
```

#### Claude

```text
In the fourth quarter of 2020, we celebrated the tenth anniversary of AIA's listing on the Hong Kong Stock Exchange. AIA's listing set multiple records at the time and remains the largest initial public offering in the global insurance industry to date. I am honoured and privileged to have worked alongside the members of the Board as AIA's business has continued to expand during this period, establishing the Company as the largest life insurer in the world by market capitalisation.
```

#### Human Reference

```text
In the fourth quarter of 2020, we celebrated the 10th anniversary of AIA’s historic listing on the Hong Kong Stock Exchange. AIA’s market debut established new records at the time and remains the largest-ever initial public offering in the global insurance sector. It has been my honour and pleasure to work alongside our Board members as our business has gone from strength to strength over this time to become the largest life insurance company in the world by market capitalisation.
```

### S06 | page 11

- unit_ids: `p11_g02, p11_b7`
- token_f1: `0.7132`
- sequence_ratio: `0.7162`

#### Source ZH

```text
董事會的所有非執行董事均由獨立人士出任，他們在公營和私營產業擁有廣泛的管治和領導經驗。我們同心協力，銳意維持奉行最高國際企業管治標準的公司文化。我們深信根深蒂固的企業管治文化，加上穩健的風險管理架構，是每家機構可持續發展的基礎。
```

#### Claude

```text
All of the Board's non-executive directors are independent and bring extensive governance and leadership experience from both the public and private sectors. Together, we are committed to maintaining a corporate culture that upholds the highest international standards of corporate governance. We firmly believe that a deeply embedded governance culture, combined with a robust risk management framework, forms the foundation for the sustainable development of any institution.
```

#### Human Reference

```text
All of the Board’s non-executive directors are independent and have extensive governance and leadership experience in the public and private sectors. Together, we are committed to maintaining a culture that upholds the highest international standards of corporate governance. We are firm believers that a strong governance culture, supported by a sound risk management framework, is fundamental to the sustainability of every organisation.
```

### S07 | page 11

- unit_ids: `p11_g03, p11_b11`
- token_f1: `0.6519`
- sequence_ratio: `0.3047`

#### Source ZH

```text
董事會的重要責任之一是確保領導層人才輩出，並執行有效的繼任安排。我們歡迎李源祥先生於2020年6月1日接替榮休的黃經輝先生，擔任集團首席執行官兼總裁。本人謹代表董事會向李源祥先生及其管理層團隊深表謝意，他們在這段前所未見的環境發揮優秀的管理才能，帶領我們的業務向前邁進。我們也衷心感謝黃經輝先生多年來的卓越領導及對友邦保險所作出的重大貢獻。
```

#### Claude

```text
One of the Board's key responsibilities is to ensure a strong pipeline of leadership talent and effective succession arrangements. We welcomed Mr Lee Yuan Siong, who succeeded the retiring Mr Ng Keng Hooi as Group Chief Executive and President on 1 June 2020. On behalf of the Board, I extend my sincere gratitude to Mr Lee and his management team for their outstanding stewardship in navigating our business through this unprecedented environment. We also express our heartfelt thanks to Mr Ng for his exceptional leadership and significant contributions to AIA over many years.
```

#### Human Reference

```text
An important responsibility for the Board is to ensure a robust leadership pipeline and effective succession planning. We welcomed Lee Yuan Siong as Group Chief Executive and President on 1 June 2020, following the retirement of Ng Keng Hooi. On behalf of the Board, I would like to thank Yuan Siong and his senior management AND team for their outstanding stewardship of our businesses in these extraordinary times. We are also very grateful to Keng Hooi for his valuable leadership and substantial contributions to AIA over many years.
```

### S08 | page 11

- unit_ids: `p11_g04, p11_b17`
- token_f1: `0.5748`
- sequence_ratio: `0.3207`

#### Source ZH

```text
環境、社會及管治議題對全球的影響日形重要。我們當竭盡所能，協助推動社會邁向更美好的未來，而我們的環境、社會及管治措施在2020年再度備受肯定。根據評級機構Sustainalytics的評選，友邦保險在超過270家保險公司中排名第二，足證我們卓越的企業管治實力和質素。此外，我們繼續榮獲Institutional Shareholder ServicesInc.(ISS)頒發「Prime」環境、社會及管治企業評級(ESG Corporate Rating)，認同我們為業界可持續發展表現最佳的公司之一。我們相信我們在這方面仍需採取更多措施，為社區實現更美好的成果。這仍是我個人與董事會成員、高級管理層團隊以及全體員工共同秉持的優先指標。
```

#### Claude

```text
Environmental, social and governance (ESG) issues are assuming ever-greater importance globally. We are committed to doing everything we can to help drive society towards a better future, and our ESG initiatives received further recognition in 2020. AIA was ranked second among more than 270 insurance companies by Sustainalytics, demonstrating the excellence and quality of our corporate governance capabilities. In addition, we continued to receive a "Prime" ESG Corporate Rating from Institutional Shareholder Services Inc. (ISS), recognising us as one of the industry's best performers in sustainability. We believe there is still much more we must do to deliver better outcomes for our communities. This remains a personal priority for me, the Board, the senior management team and all of our employees.
```

#### Human Reference

```text
The global impacts of Environmental, Social and Governance (ESG) issues continue to be of great significance. We remain committed to playing our part in the transition to a brighter future and our ESG efforts have been recognised again in 2020. The rating agency, Sustainalytics, ranked AIA second in our industry out of more than 270 peers, noting the strength and quality of our corporate governance. Additionally, our ESG Corporate Rating score from Institutional Shareholder Services Inc. (ISS) remains “Prime”, placing us among the best in our industry for our sustainability performance. AIA recognises that there is much more we can do in this area to achieve better outcomes for our communities and it remains a personal priority that I share with my Board colleagues, our senior management team and all our employees.
```

### S09 | page 11

- unit_ids: `p11_g05`
- token_f1: `0.7192`
- sequence_ratio: `0.5036`

#### Source ZH

```text
今天，客戶對友邦保險產品、服務及高質素建議日益增長的需求從未如此殷切。我們的策略建基於亞洲強勁的結構性增長動力，並獲多項因素支持，包括前所未見的財富創造、保障缺口迅速擴大、消費者取向持續轉變、數碼技術普及，以及市場聚焦於長遠的可持續發展。董事會充滿信心，友邦保險具備優越條件，把握區內展現的龐大機遇，在客戶及其家庭最需要的時刻提供財務保障，使其安心無憂，並同時為所有持分者創造共享價值。
```

#### Claude

```text
Today, customer demand for AIA's products, services and high-quality advice has never been more compelling. Our strategy is built upon Asia's powerful structural growth drivers and is supported by multiple factors, including unprecedented wealth creation, a rapidly widening protection gap, evolving consumer preferences, the proliferation of digital technology and a market focus on long-term sustainability. The Board is confident that AIA is exceptionally well positioned to capture the enormous opportunities emerging across the region, providing financial protection and peace of mind to customers and their families when they need it most, while creating shared value for all stakeholders.
```

#### Human Reference

```text
The growing need for AIA’s products, services and high-quality advice has never been more evident than it is today. Our strategy builds on the powerful structural drivers of growth prevalent in Asia, underpinned by unprecedented wealth creation, a rapidly expanding protection gap, evolving consumer preferences, the rise of digital technology and a focus on long-term sustainability. The Board remains confident that AIA is extremely well positioned to capture the enormous opportunities available in the region by providing our customers and their families with financial peace of mind at a time when they need it the most, while creating shared value for all our stakeholders.
```

### S10 | page 11

- unit_ids: `p11_b22, p11_b23`
- token_f1: `0.5455`
- sequence_ratio: `0.3254`

#### Source ZH

```text
最後，全賴客戶及股東的信任，友邦保險才能自上市以來表現強勁和持續增長。本人謹代表董事會全體成員，衷心感謝您們一直以來的支持。
```

#### Claude

```text
Finally, it is the trust of our customers and shareholders that has enabled AIA's strong and sustained growth since our listing. On behalf of all members of the Board, I extend my sincere thanks for your continued support.
```

#### Human Reference

```text
Finally, AIA’s strong performance and growth since our initial public offering would not have been possible without the trust of our customers and shareholders. On behalf of the entire Board, I am deeply grateful for your enduring support.
```

### S11 | page 13

- unit_ids: `p13_g01, p13_b3`
- token_f1: `0.592`
- sequence_ratio: `0.2415`

#### Source ZH

```text
友邦保險是客戶誠可信賴的夥伴，讓客戶在關注財務安全和家庭保障時仍可安心無憂。儘管2019冠狀病毒病大流行的影響深遠，但我衷心感謝我們的員工、代理和合作夥伴在適應新工作方式並確保為客戶提供無間斷的支援時，展現靈活應變的能力和克盡己職的精神。
```

#### Claude

```text
AIA is a trusted partner to our customers, providing them with peace of mind as they focus on their financial security and family protection. Despite the far-reaching impact of the COVID-19 pandemic, I am deeply grateful to our employees, agents and partners for demonstrating remarkable adaptability and dedication in adjusting to new ways of working while ensuring uninterrupted support for our customers.
```

#### Human Reference

```text
AIA is a trusted partner to our customers, providing peace of mind when they are concerned about the financial security and well-being of their families. While the impacts of the COVID-19 pandemic have been far-reaching, my deepest gratitude goes to our employees, agents and partners for their tremendous agility and dedication as they adapted to new working practices and ensured uninterrupted customer support.
```

### S12 | page 13

- unit_ids: `p13_g02, p13_b8`
- token_f1: `0.6557`
- sequence_ratio: `0.194`

#### Source ZH

```text
自疫情大流行開始以來，本集團的各業務團隊反應迅速，積極協助紓緩對社區的影響，同時確保員工安全。本集團為此廣泛採取多項措拖，包括財政支持、提供醫療物資、免費保障覆蓋、獲取醫療保健資源、精簡服務流程和加快理賠支付，令我引以為榮。我們一如既往找出每一個可以作出理賠的理由，年內已支付逾160億美元的保險給付及理賠，為客戶提供極其重要的財務保障。
```

#### Claude

```text
Since the onset of the pandemic, our business teams across the Group have responded swiftly and proactively to help mitigate the impact on our communities while ensuring the safety of our employees. I am proud of the extensive range of measures we have implemented, including financial support, provision of medical supplies, complimentary coverage, access to healthcare resources, streamlined service processes and accelerated claims payments. True to our commitment to finding every reason to pay, we paid over US$16 billion in insurance benefits and claims during the year, providing critically important financial protection to our customers.
```

#### Human Reference

```text
Since the onset of the pandemic, our businesses have responded quickly and proactively to help alleviate the impact on our communities, while ensuring the safety of our people. I am immensely proud of the wide-ranging initiatives undertaken including financial support, provision of medical supplies, free protection cover, access to health resources, streamlined services and expedited claim payments. We always look for every reason to pay a claim and, over the year, we paid more than US$16 billion in benefits and claims, providing vital financial protection for our customers.
```

### S13 | page 13

- unit_ids: `p13_g03, p13_b13`
- token_f1: `0.5893`
- sequence_ratio: `0.2724`

#### Source ZH

```text
儘管為遏制2019冠狀病毒病傳播的措施導致新業務價值減少至27.65億美元，但隨著外出限制放寬，銷售動力轉趨正面，並在2021年展開非常強勁的勢頭，首兩個月的新業務價值按年增長15%。我們規模龐大和持續增長的有效保單組合所帶來的高質素和經常性收入來源，帶動2020年稅後營運溢利增加5%，期內產生的基本自由盈餘則增長7%。截至2020年12月31日，內涵價值權益創新高，達672億美元，集團當地資本總和法覆蓋率為374%，足證我們雄厚的資本實力和嚴謹的財務管理。
```

#### Claude

```text
Although measures to contain the spread of COVID-19 resulted in VONB declining to US$2,765 million, sales momentum turned positive as mobility restrictions eased and has commenced 2021 with very strong momentum, with VONB for the first two months growing 15 per cent year-on-year. The high-quality recurring income streams generated by our large and growing in-force portfolio drove a 5 per cent increase in OPAT for 2020, while UFSG for the period grew 7 per cent. As at 31 December 2020, EV Equity reached a record US$67.2 billion and the Group's LCSM coverage ratio stood at 374 per cent, demonstrating our robust capital strength and rigorous financial stewardship.
```

#### Human Reference

```text
While value of new business (VONB) was affected by COVID-19 containment measures, reducing to US$2,765 million, we delivered positive sales momentum as movement restrictions eased and made a very strong start AND to 2021 with 15 per cent year-on-year VONB growth in the first two months. Our large and growing in-force portfolio with high-quality, recurring sources of earnings delivered a 5 per cent increase in operating profit after tax (OPAT) in 2020 and a 7 per cent increase in underlying free surplus generation (UFSG). EV Equity reached a new high of US$67.2 billion and the Group LCSM cover ratio was 374 per cent as at 31 December 2020, demonstrating our robust capital position and disciplined financial management.
```

### S14 | page 13

- unit_ids: `p13_b14, p13_b15`
- token_f1: `0.6809`
- sequence_ratio: `0.5742`

#### Source ZH

```text
董事會建議2020年末期股息增加7.5%至每股100.30港仙。這秉承友邦保險行之已久的審慎、可持續及漸進的派息政策，讓本集團可把握未來的增長機遇，並且保持財務靈活性。
```

#### Claude

```text
The Board has proposed a 7.5 per cent increase in the 2020 final dividend to 100.30 Hong Kong cents per share. This is consistent with AIA's long-standing prudent, sustainable and progressive dividend policy, which enables the Group to capture future growth opportunities while maintaining financial flexibility.
```

#### Human Reference

```text
The board of Directors (Board) has recommended a 7.5 per cent increase in the final dividend for 2020 to 100.30 Hong Kong cents per share. This follows AIA’s established prudent, sustainable and progressive dividend policy, allowing for future growth opportunities and the financial flexibility of the Group.
```

### S15 | page 13

- unit_ids: `p13_g04, p13_b19`
- token_f1: `0.6369`
- sequence_ratio: `0.1367`

#### Source ZH

```text
友邦保險具有多項顯著優勢，讓我們在競爭激烈的市場別樹一幟。我們在亞洲經營數十載，擁有區內無可比擬的平台，並於我們業務所在的大部分市場雄踞領導地位。我們始終如一地百分百專注於亞洲市場，有助我們在全球最具吸引力的壽險業地區全面把握增長機遇。這份專注結合我們領導團隊在亞洲的豐富經驗及員工的優秀質素，一直是我們表現卓越的重要動力。
```

#### Claude

```text
AIA possesses multiple distinctive advantages that set us apart in a competitive marketplace. Our decades of operating experience in Asia have created an unparalleled platform across the region, with leadership positions in most of the markets where we operate. Our unwavering 100 per cent focus on Asia enables us to fully capture growth opportunities in the world's most attractive life insurance region. This focus, combined with our leadership team's deep experience in Asia and the outstanding quality of our people, has been a vital driver of our exceptional performance.
```

#### Human Reference

```text
AIA has many significant advantages that differentiate us from our competitors. We have an unparalleled platform in Asia built up over many decades and hold leading positions in the majority of our markets. Our 100 per cent focus on Asia will not change and enables us to capture the full growth opportunities available in the world’s most attractive region for life insurance. This focus, combined with the extensive experience of our leadership team in Asia and the quality of our people, has been an important driver of our success.
```

### S16 | page 13

- unit_ids: `p13_g05`
- token_f1: `0.6875`
- sequence_ratio: `0.4259`

#### Source ZH

```text
我們無可比擬的分銷實力能直接接觸客戶，並提供高質素的專業建議，協助滿足亞洲消費者龐大且日益增長的長期保障和儲蓄需求。如今大眾比以往更期望企業能以符合長遠可持續發展的方式應對他們的需要。友邦保險擁有市場領先的品牌，以幫助大眾實踐健康、長久、好生活的目標為基礎。
```

#### Claude

```text
Our unparalleled distribution strength provides direct customer access and high-quality professional advice, helping to meet the substantial and growing long-term protection and savings needs of Asian consumers. Today, people expect more than ever that companies will address their needs in a manner consistent with long-term sustainability. AIA has a market-leading brand built upon our Purpose of helping people live Healthier, Longer, Better Lives.
```

#### Human Reference

```text
Our unrivalled distribution provides direct access to customers, delivering high-quality professional advice to help address the significant and growing long-term protection and savings needs of consumers in Asia. Now more than ever, people expect companies to respond in a way that is aligned with long-term sustainability. AIA has a market-leading brand that is underpinned by our Purpose of helping people live Healthier, Longer, Better Lives.
```

### S17 | page 13

- unit_ids: `p13_g06, p13_b25`
- token_f1: `0.6719`
- sequence_ratio: `0.5151`

#### Source ZH

```text
我們旨在使友邦保險在科技應用方面領先全球，加強互聯互通，擴大規模和提升效率。更深入瞭解數據分析有助我們締造獨特和個人化的客戶體驗。切合和反映個人需求和生活方式的產品及服務，改變了大眾對人壽保險的看法，為我們與客戶建立長遠關係奠定堅實的基礎。
```

#### Claude

```text
We aim to position AIA as a global leader in technology adoption, enhancing connectivity, expanding scale and improving efficiency. Deeper insights from data analytics enable us to create distinctive and personalised customer experiences. Products and services that are relevant to and reflect individual needs and lifestyles are transforming perceptions of life insurance, establishing a solid foundation for building enduring relationships with our customers.
```

#### Human Reference

```text
Our aim is to position AIA as a global leader in the use of technology, embracing greater connectivity, scale and efficiency. Deeper insights from data analytics enable distinctive and personalised customer experiences. Products and services that are relevant and reflect an individual’s needs and lifestyle change the way life insurance is perceived and provide a strong basis for developing long-term relationships with our customers.
```

### S18 | page 13

- unit_ids: `p13_g07`
- token_f1: `0.6667`
- sequence_ratio: `0.2539`

#### Source ZH

```text
儘管2020年是前所未見的一年，但我對亞洲壽險行業的前景和友邦保險的未來比以往更為樂觀。我們繼續挑戰自己，發展我們的優先任務，以確保我們能繼續適切地迎合客戶期望和財務需求的轉變。我們的全新企業策略建基於友邦保險的現有實力，推進轉型過程，以在未來為客戶提供最佳的服務。
```

#### Claude

```text
Although 2020 was an unprecedented year, I am more optimistic than ever about the prospects for Asia's life insurance industry and AIA's future. We continue to challenge ourselves and evolve our priorities to ensure we remain responsive to changing customer expectations and financial needs. Our new corporate strategy builds upon AIA's existing strengths and advances our transformation journey to deliver the best possible service to our customers in the years ahead.
```

#### Human Reference

```text
While 2020 was an unprecedented year, it has made me more optimistic than ever about the prospects for the life insurance industry in Asia and the future of AIA. We continue to challenge ourselves and develop our priorities to ensure that we remain highly relevant to our customers as their expectations and financial needs evolve. Our new corporate strategy builds on AIA’s existing strengths and enables the transformation that we will make to best serve our customers well into the future.
```

### S19 | page 14

- unit_ids: `p14_g01, p14_b7`
- token_f1: `0.7514`
- sequence_ratio: `0.6034`

#### Source ZH

```text
友邦保險中國業務在2020年為本集團新業務價值帶來最大貢獻，並在2021年初表現卓越，與2020年同期比較，今年首兩個月錄得非常強勁的新業務價值增長。儘管2020年的9.68億美元新業務價值較2019年下降17%，但這主要由於2019冠狀病毒病在首季爆發初期新銷售有限所致。年內稅後營運溢利增長14%，主要是由於我們日益增長的有效保單組合及有利的理賠經驗。
```

#### Claude

```text
AIA China delivered the largest contribution to the Group's VONB in 2020 and has performed exceptionally well in early 2021, recording very strong VONB growth in the first two months of the year compared with the prior year. Although VONB of US$968 million for 2020 declined 17 per cent from 2019, this was primarily due to limited new sales in the first quarter during the initial outbreak of COVID-19. OPAT for the year increased 14 per cent, driven mainly by our growing in-force portfolio and favourable claims experience.
```

#### Human Reference

```text
AIA China became the largest contributor to the Group’s VONB in 2020 and delivered a successful start to 2021 with very strong VONB growth in the first two months of the year compared with the same period in 2020. While VONB of US$968 million for 2020 was 17 per cent lower than 2019, this was mostly due to limited new sales during the initial outbreak of COVID-19 in the first quarter. OPAT increased by 14 per cent for the year, primarily driven by growth in our in-force portfolio and favourable claims experience.
```

### S20 | page 14

- unit_ids: `p14_g02`
- token_f1: `0.6815`
- sequence_ratio: `0.485`

#### Source ZH

```text
在2020年，我們成功獲得監管機搆批復，將上海分公司改建為中國內地首家外資獨資人身保險子公司。於2021年3月，我們已獲得中國銀行保險監督委員會批復，准予在四川省開業。四川省是中國內地以國內生產總值計的第六大省份，以人口計為第四大省，為友邦保險帶來重大的長期增長機遇。
```

#### Claude

```text
In 2020, we successfully obtained regulatory approval to convert our Shanghai Branch into Mainland China's first wholly foreign-owned life insurance subsidiary. In March 2021, we received approval from the China Banking and Insurance Regulatory Commission to commence operations in Sichuan Province. Sichuan is Mainland China's sixth-largest province by gross domestic product and fourth-largest by population, presenting significant long-term growth opportunities for AIA.
```

#### Human Reference

```text
In 2020, we successfully obtained regulatory approval and completed the conversion of our Shanghai branch to become the first wholly foreign owned life insurance subsidiary in Mainland China. In March 2021, we received approval from the China Banking and Insurance Regulatory Commission (CBIRC) to begin operations in Sichuan. Sichuan is the sixth largest province by GDP in Mainland China and the fourth largest by population, representing a significant long-term growth opportunity for AIA.
```
