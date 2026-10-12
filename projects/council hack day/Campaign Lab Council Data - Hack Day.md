# 🗄️ Campaign Lab Challenge Sheet

# **🗄️Campaign Lab Council Data Hack Day Challenge Sheet 🗄️**

### 

### **Link to this Document: [https://qr-taupe-psi.vercel.app/s/Ehhxsm8](https://qr-taupe-psi.vercel.app/s/Ehhxsm8)** 

### **![][image1]** **Github: [Here](https://github.com/CampaignLab)**  **Events Calendar: [Here](https://luma.com/CampaignLab)** 

### **Whatsapp: [Here](https://chat.whatsapp.com/COM4FaWTklG3OcGAmQa44Z%20)** 

Why we are here: [https://docs.google.com/presentation/d/1Tuu4pB\_36j91bgWuThCPwXAIQnJM6oJ3yxJbxrM\_BZI/edit?usp=sharing](https://docs.google.com/presentation/d/1Tuu4pB_36j91bgWuThCPwXAIQnJM6oJ3yxJbxrM_BZI/edit?usp=sharing) 

Data: [https://docs.google.com/presentation/d/19s8U08250CpenHYD-KVFk2gJUNtzvY3LiOMuDOAPybE/edit?slide=id.p9\#slide=id.p9](https://docs.google.com/presentation/d/19s8U08250CpenHYD-KVFk2gJUNtzvY3LiOMuDOAPybE/edit?slide=id.p9#slide=id.p9) 

**If you need api keys/ tokens \- ask Hannah or Noam\!**

---

**📋[Agenda]()**

**📊[Datasets]()**

**📝[Register Your Team](https://team-showcase-vote.vercel.app/)**

**🔍[Table A Data Collection]()**

*We have successfully built scrapers and data collection for a wide range of sources. But there are councils we can't reach, scrapers that have fallen over and potentially useful sections that are not yet being scraped. These Challenges focus on improving the way we collect data.* 

**🕵️[Table B Opposition Research]()**

*Can we dig into the data and use it to find useful information for campaigners? Can we dig up dirt on Reform and help to arm campaigners with information that could be relevant for their campaigns.* 

**🏛️[Table C Representation]()**

*There is lots of data here that helps the public understand their constituents better. Can we pull that data to help make councils more representative and accountable to the citizens it represents.*

**🪟[Table D Transpar ency]()**

*Campaigning organisations and charities can find lots of useful data that could support or inform their campaigns. Can we help the progressive ecosystem get the most out of this data?*

**⚖️[Table E Comparison]()**

*These new datasets allow us to look at comparative decision making across different local authorities. Can we create displays that can help councils find areas of comparative advantage and find good models to improve their systems?*

**🪶[Table F Constitution]()**

*Councils are confusing and endless waves of local government reform ensure a rapid pace of change. Can we build tools to keep on top of this transformation and find data about the structure and constitution of councils that can help the public have a better understanding of what our councils are and how they work?*

# 📋 Agenda

# **📋Agenda**

**🚪11:00 Doors Open** 

**👋11:05 Welcome & why we are here** 

**🔍11:20 Forming Teams & Choosing Challenges** 

**🔒12:00 Project Lock in**

**🥯12:30 Lunch** 

**⏱️17:00 Final Commit**

**🗳️17:10 Demonstrations & Voting**

**🏆18:00** **Awards** 

**🍕19:00 Dinner & Social** 

**🫡21:00 Doors Close** 

# 🙋 How to get stuck in

# **🙋 How to get stuck in**

Pick a track depending on what you fancy building. They're not exclusive — most projects will mix a couple. For full detail on the datasets themselves (files, formats, servers), see the [Getting the Data](https://docs.google.com/document/d/1AlHcRH1yX8uk6-K6NZf7Gy3n5KnHBzHgFZLCfmoomrQ/edit) doc.

[01](#heading=h.sijlronb) — Building the infrastructure  
[02](#heading=h.kdafrfzg) — Building on the search & get API  
[03](#heading=h.ewixsqyt) — Exploring the data — online  
[04](#heading=h.wazvevcg) — Exploring the data — local

## **01 — Building the infrastructure**

[**github.com/democracyclub/lgsf**](https://github.com/democracyclub/lgsf)  
LGSF (Local Government Scraper Framework) is Democracy Club's open-source toolkit for turning UK council websites into open data — and it's where this scraping effort is headed. Each of the \~440 councils is a directory holding a *metadata.json* and one Python file per data type; three types exist so far (councillors, minutes, decisions). Most councils run one of two content management systems (ModernGov or CMIS), so a council's scraper is often just a two-line subclass of the right base class — custom HTML scrapers cover the rest. HTTP clients are pluggable per scraper, from a Rust client with a Firefox TLS fingerprint (the default) up to headless Chromium for sites behind Cloudflare or Incapsula.  
**Good if you like:** Python, scraping, fixing broken things, and leaving the ecosystem better than you found it — adding councils, repairing scrapers, or building a whole new data type.  
**Setup** (needs Python 3.12 and [uv](https://docs.astral.sh/uv/)):  
git clone https://github.com/DemocracyClub/LGSF.git  
cd LGSF  
uv sync

\# smoke test: scrape one small council's meetings  
uv run python manage.py minutes \--council ADU \-v \--skip-documents

That writes meetings to *data/ADU/Minutes/* — no API keys or config needed. The repo's *docs/* folder covers running scrapers, finding councils that need work, and each scraper type; there are also agent skills under *.claude/skills/* if you're working with Claude Code or similar. Fair warning from the maintainers: the project is alpha and everything may change — the [Democracy Club Slack](https://slack.democracyclub.org.uk/) is the place to talk about it.

## **02 — Building on the search & get API**

[**councilgateway.poteris.co.uk/council-api**](https://councilgateway.poteris.co.uk/council-api)  
A hosted, read-only JSON API over everything scraped so far: hundreds of councils, \~130k meetings, \~1.6M documents with extracted text, and \~180k decisions — plus full-text search over the whole corpus. No API key, no rate-limit hoops, reachable from anywhere (including Colab). There's also a browsable webapp at the parent URL, [councilgateway.poteris.co.uk](https://councilgateway.poteris.co.uk).  
**Good if you like:** building apps, bots, or analyses on live data without ever touching a multi-gigabyte CSV.  
**Setup:** none. Open the interactive docs at [/council-api/docs](https://councilgateway.poteris.co.uk/council-api/docs) and try queries in the browser, or:  
curl "https://councilgateway.poteris.co.uk/council-api/search?q=pedestrian+crossing\&size=5"

Endpoints: /councils, /meetings, /documents, /decisions, /people, and /search (two modes: *document* searches extracted text, *classification* searches AI summaries). From any hit, /documents/{id}/file redirects to a download of the original PDF. Worked examples — including search-to-PDF in five lines of Python — are in the Getting the Data tab.

## **03 — Exploring the data — online**

**Google Colab \+ Google Drive**  
The CSV dumps (document text included) live in the [2026-08-22 Hackday Drive folder](https://drive.google.com/drive/u/0/folders/123jtFAZUMr2NQTq1hEhMct49r337Mexg), and Colab can read them in place — nothing to download, nothing to install, easy to share your notebook afterwards.  
**Good if you like:** pandas, plotting, and NLP experiments with zero local setup.  
**Setup:**  
1\. In Drive, right-click the hackday folder → Organise → Add shortcut to My Drive.  
2\. Start a notebook at [colab.research.google.com](https://colab.research.google.com) and run:  
from google.colab import drive  
drive.mount('/content/drive')

import pandas as pd  
df \= pd.read\_csv('/content/drive/MyDrive/2026-08-22 Hackday/minutes\_documents\_last\_day.csv')  
df.head()

3\. Start with the two small *last\_day* files, then scale up. The hosted API works from Colab too — including original PDFs via /documents/{id}/file. (The one thing Colab can't reach is the local document server in the room.)

## **04 — Exploring the data — local**

**Download from the local server**  
On the venue network, the document server at **http://council-data.localdomain:3923** (or **http://192.168.1.120:3923**) serves fast local copies of the CSVs and all \~1.5 TB of original PDFs — no Google sign-in, LAN speed.  
**Good if you like:** working on your own machine with your own tools, or projects that need the actual PDFs (layout, tables, OCR...).  
**Setup:** grab a CSV — the small ones are [minutes\_documents\_last\_day.csv](http://council-data.localdomain:3923/minutes_documents_last_day.csv) (5.7 MB) and [decisions\_documents\_last\_day.csv](http://council-data.localdomain:3923/decisions_documents_last_day.csv) (2.6 MB); the full list with sizes is in the [Getting the Data](https://docs.google.com/document/d/1AlHcRH1yX8uk6-K6NZf7Gy3n5KnHBzHgFZLCfmoomrQ/edit) doc. Then any row's **file\_name** value fetches its original PDF:  
curl \-o mydoc.pdf http://council-data.localdomain:3923/j78wt1qe9q4m38tv8wsyibk3xjum

Be gentle with it — it's a Raspberry Pi. Directory listing is off by design: fetch the specific documents you need by ID rather than bulk-downloading, and ask Peyman first if you think you need a big batch.

# 📊 Datasets Read This First\!

# **Getting the Data**

Everything for the hackday lives in three main places:

* **Google Drive** — CSV extracts of council meeting documents, including full extracted text: [2026-08-22 Hackday Folder](https://drive.google.com/drive/u/0/folders/123jtFAZUMr2NQTq1hEhMct49r337Mexg)  
* **Council Gateway Webapp & API** — browse and query online at [councilgateway.poteris.co.uk](https://councilgateway.poteris.co.uk) (no downloads needed)  
* **Local Document Server** — original PDFs (\~1.5 TB) fetchable by ID, plus fast local CSV copies  
* **Scraping Architecture** \- [https://github.com/DemocracyClub/LGSF](https://github.com/DemocracyClub/LGSF) 

## **Quickstart (5 minutes)**

1\. Download the two small single-day files: **minutes\_documents\_last\_day.csv** (5.7 MB) and **decisions\_documents\_last\_day.csv** (2.6 MB) — from the Drive folder, or on the hackday network faster from the local server (links in the table below). They contain all documents for meetings/decisions dated 19 August 2026 — small enough to experiment with on any laptop.

2\. Load one in Python:

| `import pandas as pddf = pd.read_csv("minutes_documents_last_day.csv")print(df.shape)                    # (322, 15)print(df.columns.tolist())print(df.iloc[0].file_text[:500])  # extracted text of the first document` |
| :---- |

3\. Once that works, scale up to the bigger CSVs, query the hosted API, and/or pull original PDFs from the local server — see below.

## **The data files**

All of these files are hosted in the [Hackday Drive folder](https://drive.google.com/drive/u/0/folders/123jtFAZUMr2NQTq1hEhMct49r337Mexg) (downloadable from anywhere). The filenames in the table below link directly to the local document server for high-speed local network downloads.

| File | Size | Description |
| :---- | :---- | :---- |
| [minutes\_documents\_last\_day.csv](http://council-data.localdomain:3923/minutes_documents_last_day.csv) | 5.7 MB | Minutes documents for meetings on 19 Aug 2026 (322 rows). Start here. |
| [decisions\_documents\_last\_day.csv](http://council-data.localdomain:3923/decisions_documents_last_day.csv) | 2.6 MB | Decision documents dated 19 Aug 2026 (99 rows). Start here. |
| [minutes\_documents\_last\_month.csv](http://council-data.localdomain:3923/minutes_documents_last_month.csv) | 407 MB | Minutes documents for meetings 22 Jul – 20 Aug 2026 (17,391 rows). |
| [decisions\_documents.csv](http://council-data.localdomain:3923/decisions_documents.csv) | 544 MB | The complete decisions dump (26,933 rows, Jan 2023 – Aug 2026). |
| [meetings\_documents.csv](http://council-data.localdomain:3923/minutes_documents.csv) | 37 GB | The complete minutes dump, sorted by meeting\_date (Nov 2023 – Aug 2026). Named minutes\_documents.csv on the local server. |

## **CSV format**

Each row represents one document attached to a meeting (minutes files) or a decision (decisions files). Key fields include:

* **file\_text** — Full extracted text of the document. For most text work, the PDF is unnecessary.  
* **file\_name** — Document ID (an opaque 28-character key, e.g., *j78wt1qe9q4m38tv8wsyibk3xjum*). Used to fetch the original PDF from the local server.  
* **Metadata fields** — Minutes files include *council\_name*, *committee\_name*, *meeting\_name*, *meeting\_date*, *meeting\_source\_url*, *document\_kind*, *document\_name*, classification flags (*contains\_agenda*, *contains\_attendees*, *contains\_decisions*, *is\_minutes*, *is\_media*), and *source\_url\_discouraged\_for\_use*. Decisions files contain similar fields plus *decision\_purpose* and *decision\_date*.

**Gotchas:**

* **Multiline fields:** *file\_text* contains newlines inside quoted fields, so line-based tools (grep, wc \-l, split) will mangle rows. Always use a real CSV parser like pandas.  
* **Python CSV limit:** If using Python's *csv* module directly, raise the field size limit first: `import csv, sys; csv.field_size_limit(sys.maxsize)`  
* **Defanged URLs:** The *source\_url\_discouraged\_for\_use* column is deliberately modified (hxxps://) to prevent re-scraping council websites during the hackday, as all files are served locally.

For larger files, process in chunks rather than loading everything into memory at once:

| `for chunk in pd.read_csv("minutes_documents_last_month.csv", chunksize=1000):    ...  # each chunk is a DataFrame of 1000 rows` |
| :---- |

## **Browse and Query Online — Webapp & API**

If you'd rather explore than download, use the hosted Council Gateway:

* **Webapp:** [https://councilgateway.poteris.co.uk](https://councilgateway.poteris.co.uk) — explore councils, meetings, documents, and decisions.  
* **Read-only JSON API:** [https://councilgateway.poteris.co.uk/council-api](https://councilgateway.poteris.co.uk/council-api) — full-text search over the corpus. Interactive docs: [/council-api/docs](https://councilgateway.poteris.co.uk/council-api/docs). No API key required.

| `curl "https://councilgateway.poteris.co.uk/council-api/councils?page=1"` |
| :---- |

The API is reachable from anywhere — including Colab — and is the easiest way to do targeted lookups or full-text search without touching the big CSVs. Use the CSVs when you want to crunch everything in bulk.

## **Full-text search via the API**

The API can search the entire document corpus — no CSV downloading needed. Try it interactively at [/council-api/docs](https://councilgateway.poteris.co.uk/council-api/docs), or:

| `curl "https://councilgateway.poteris.co.uk/council-api/search?q=pedestrian+crossing&size=5"` |
| :---- |

**Parameters:**

* **q** — the search query (required, at least 2 characters)  
* **mode** — *document* (default) searches the extracted text of the documents themselves; *classification* searches AI-generated summaries of each document (topline summary, keywords, attendees, decisions) — better for "what was discussed" questions  
* **council\_id** — restrict to one council (get IDs from /councils)  
* **size** / **offset** — pagination (default 20 per page; total caps at 10,000, so read that as "10,000+")

Each hit comes with a relevance score, the meeting context, highlight snippets showing your terms in \<strong\> tags, and the document's database record. The record's id unlocks the detail endpoints: /documents/{id}, /documents/{id}/classifications, and /documents/{id}/file — which redirects to a download of the original PDF. **That last one works from anywhere, including Colab** (it serves from cloud storage, not the room server).

End-to-end in Python — search, list the hits, download the top hit's PDF:

| `import requestsAPI = "https://councilgateway.poteris.co.uk/council-api"r = requests.get(f"{API}/search", params={"q": "pedestrian crossing", "size": 5})r.raise_for_status()results = r.json()print(results["total"], "matches")for hit in results["hits"]:    print(f'{hit["score"]:6.1f}  doc {hit["record"]["id"]}  {hit["source"]["meeting_name"]}')best_id = results["hits"][0]["record"]["id"]pdf = requests.get(f"{API}/documents/{best_id}/file")  # redirects to the PDFopen(f"{best_id}.pdf", "wb").write(pdf.content)` |
| :---- |

## **Original PDFs — Local Document Server**

All original PDFs are served on the hackday network at **http://council-data.localdomain:3923** (use **http://192.168.1.120:3923** if the hostname doesn't resolve). It is only reachable from the local network — not from the internet or Colab.

To fetch a document, take the **file\_name** value from any CSV row and request it directly:

| `curl -o mydoc.pdf http://council-data.localdomain:3923/j78wt1qe9q4m38tv8wsyibk3xjum` |
| :---- |

End-to-end in Python — pick a row from a CSV, look up its PDF:

| `import pandas as pd, requestsBASE = "http://council-data.localdomain:3923"df = pd.read_csv("decisions_documents_last_day.csv")row = df.iloc[0]print(row.council_name, "|", row.decision_purpose[:100])doc_id = row.file_name          # e.g. cv2n79r3stkt7rsl34ttmjon86ldresp = requests.get(f"{BASE}/{doc_id}", timeout=120)resp.raise_for_status()with open(f"{doc_id}.pdf", "wb") as f:    f.write(resp.content)print("saved", doc_id + ".pdf,", len(resp.content), "bytes")` |
| :---- |

**Please be gentle with it:** it's a Raspberry Pi with a 1.5 TB disk holding millions of files. Directory listing is disabled on purpose — fetch the specific documents you need by ID rather than trying to browse or bulk-download. There is no point mirroring the whole thing; if you think you need a large batch, ask Peyman first.

## **Two ways of working**

**Option A — on your laptop.** Download the CSVs you need (table above) and work locally. Being on the Newspeak network, you can also pull original PDFs from the document server as shown above.

**Option B — Google Colab (no downloads to your machine).** In Drive, right-click the hackday folder → Organise → Add shortcut to My Drive. Then in a Colab notebook the files are readable directly:

| `from google.colab import drivedrive.mount('/content/drive')import pandas as pddf = pd.read_csv('/content/drive/MyDrive/2026-08-22 Hackday/minutes_documents_last_day.csv')` |
| :---- |

Remember Colab can't reach the local document server — but it can use the hosted API, including /documents/{id}/file for original PDFs, and the CSVs' file\_text column is usually all you need.

## **Where to put your work**

Please add anything you produce to the **"[Hackday work and outputs \- add here\!](https://drive.google.com/drive/u/0/folders/1JCZJ_UzLEUZxi-mM9aWOXvp1g1vkyZqJ)"** subfolder in the Drive folder.

# 🔍 Table A Data Collection

# **🔍Table A Data Collection**

*We have successfully built scrapers and data collection for a wide range of sources. But there are councils we can't reach, scrapers that have fallen over and potentially useful sections that are not yet being scraped. These Challenges focus on improving the way we collect data.* 

**Broken Councilor Page scrapers**

Not long ago we were able to scrape the councillor pages from all councils in the UK. But some of our scrapers are broken. Can you fix them?

Restore at least one broken councillor-page scraper and document the failure mode so the fix can be reused across councils using the same platform. Stretch goal: add a simple test that alerts us when a scraper breaks again.

**Link to Scrapers:**  
[https://github.com/DemocracyClub/LGSF](https://github.com/DemocracyClub/LGSF)

**Link to Tracker that shows what scrapers are broken:** [https://democracyclub.github.io/lgsf-dashboard/](https://democracyclub.github.io/lgsf-dashboard/) 

---

**Scraping the rest of the Council Minutes**

Council Minutes are the core of the dataset but there are some councils that are missing and have not yet been added to the dataset. Can you set up scrapers for the locations we are not yet scraping?

---

**Scraping Registers of Interests** 

Every council has to publish a register of interests but we don't currently have scrapers set up to retrieve that information. Can we find a team that can build a working scraper to retrieve that information?

---

**Decisions** 

Councils are required to keep a public record of important decisions made. Usually these councils maintain a page on their website with these decisions. We have scrapes of some decision pages but lots of councils use unconventional pages. Can we expand the scope of our decision scrapers to collect more information and help to build out the database.

---

**Constitutions**

Most councils have constitutions which spell out their political structure but these are often different and buried. Can we fix this problem by collecting council constitutions in a structured way and test whether we can extract comparable information such as committee responsibilities, delegated powers, call-in rules and public participation rights.

---

**Contracts**

Councils often publish contracts on their websites, can we take the time to scrape this information. Can we pull together this dataset because it would open lots of opportunities for searching for conflicts of interest. 

---

**Council Surgery Finder**

Most councillors arrange surgeries where members of the public can come in and meet their representatives. Dates and times can sometimes be hard to find. Can we locate and scrape surgery times and make a searchable repository by postcode to help people attend surgeries.

---

**Town & Parish Councils**

Town and parish councils collectively raise substantial sums through the council tax precept but receive relatively little systematic scrutiny. Can we build a first-pass inventory or scraper for town and parish councils, starting with a manageable geography, and test what useful data can be collected consistently. This is a genuinely new dataset, so even mapping the landscape and identifying reusable patterns would be a valuable output. 

# 🕵️ Table B Opposition Research

# **🕵️Table B Opposition Research**

*Can we dig into the data and use it to find useful information for campaigners? Can we dig up dirt on Reform and help to arm campaigners with information that could be relevant for their campaigns.* 

**Funding cuts alert**

Refugee groups, unions and other progressive causes would find it very useful to have advanced warning of when their funding could be cut or closed. Can we build an alerting tool that identifies proposed cuts, closures or material reductions in council funding before they are implemented. Extract the affected service/organisation, amount, decision stage and meeting date, with configurable themes such as jobs, refugee support, climate programmes or flood defences.

---

**Reform, Restore & Tory statements researcher?**

Can we create a tool that collates statements made by reform and conservative members and then build a search that allows us to surface controversial or embarrassing statements.  Councillors saying stupid things can also build a fun effective front end for this.

---

**Improved attendance tracker**

Our attendance tracker monitors cllr attendance at meetings but it does so imperfectly. Can we improve the scope and quality of the data meeting records are incomplete.

Github Repo:  
[https://github.com/CampaignLab/councillor-attendance-tracker.git](https://github.com/CampaignLab/councillor-attendance-tracker.git)

---

**Council Promise & Position Tracker**

Can we extract clear public positions or commitments made by councillors and political groups, then make them searchable over time? A useful tool would connect a named person/group, issue, quote or summary, date and source so campaigners can compare what was said with what happened later.

# 🏛️ Table C Representation

# **🏛️Table C Representation**

*There is lots of data here that helps the public understand their constituents better. Can we pull that data to help make councils more representative and accountable to the citizens it represents.*

**What has the council ever done for us?**

Council wins are often buried and not widely reported. Can we collect data from council minutes that helps us keep track of the concrete wins delivered by progressives. Can we build a prototype that extracts concrete council achievements or service improvements from minutes and turns them into a searchable, source-linked record. 

---

**Councillor Diversity Statistics**

What is the gender balance of your council? How diverse is it that we can collate data on the makeup of councils? Can we then look at how representative of your area is to identify  gaps in community representation?

---

**Issue Tracker**

Do councils spend more time discussing healthcare or high streets? Can we break down the and classify council agenda items and minutes by topic and build a simple view showing what different councils spend their formal meeting time discussing.

---

**How did They Vote**

Councillors will often vote on a range of issues and these votes are frequently recorded in the minutes of meetings. Can we track councillors and how they voted to create a tool that makes it easier for the public to understand what their representatives voted for?

---

**Consultation: You Said, Did They Listen?**

Link published consultation findings to subsequent cabinet or committee decisions and identify where the final decision aligns with, departs from or never addresses the consultation response. We may need to locate consultations separately through scraping but it seems possible that outcomes may be retrievable from minutes.

# 🪟 Table D Transparency

# **🪟Table D Transparency**

# *Campaigning organisations and charities can find lots of useful data that could support or inform their campaigns. Can we help the progressive ecosystem get the most out of this data.*

**Weekly Breakdown**

It's often hard for journalists and reporters to keep track of what is happening in local councils. Can we generate a weekly council briefing for a selected area: major decisions, spending, planning, service changes and notable political moments, with links back to the underlying records. Design it for a local journalist or campaigner who has five minutes to scan the week.

---

**Journalist query interface**

Journalists & campaigners often want tools to search for specific things related to stories they are working on. Can we build tools to help make the database a bit more navigable and help create a more broad querying interface? For example, suppose I want to know about comments on adult social care by a specific councillor. 

---

**Climate commitments vs actions gap** 

Climate Emergency UK have told us they would be interested in the ability to cross-reference councils that declared climate emergencies with what their minutes actually show on transport, planning, procurement. One approach would be to pick one measurable climate commitment and compare what councils say they have committed to with subsequent decisions in minutes, procurement, transport or planning.

---

**Private Equity Early-Warning Tool** 

Build a prototype that mines local council minutes to identify early warning signs of private equity consolidation and financial stress in outsourced local services. The tool would detect signals such as ownership transfers, contract novations, unusual fee increases, corporate restructuring and rapid provider expansion, cross-reference relevant companies with Companies House data. We would start by extracting provider names from minutes and compare with companies house data to try to detect signs of consolidation. This has been a particularly rampant problem in social care according to some anecdotes so it would be interesting to see what we can surface.

Companies House:  
[https://www.gov.uk/government/organisations/companies-house](https://www.gov.uk/government/organisations/companies-house)

---

**Contradiction detectors** 

Find cases where minutes record a decision that contradicts a stated council policy. The basic idea is to use the council minutes to find commitments and make a list and then look for later events or decisions that contradict that stated position.

---

**Supplier Concentration Watch**

The ideal version of this tool probably requires wider scraping but can we use the minutes we have to identify councils becoming increasingly dependent on a small number of suppliers. Surface repeated awards, rising spend and cross-council supplier concentration as a simple transparency tool.

# ⚖️ Table E Comparison

# **⚖️Table E Comparison**

*These new datasets allow us to look at comparative decision making across different local authorities. Can we create displays that can help councils find areas of comparative advantage and find good models to improve their systems?*

**Council Leaderboards on policies**

One of the most common requests we have heard from campaigners, activists and other progressives is to be able to understand council data in a comparative way. Can we create a tool that allows a user to pick a policy type (EV charging, 20mph zones, HMO licensing) and compare councils positions.

---

**Council demographics comparisons**

Can we compare council demographics? Where are the oldest councillors, the highest Paid and the lowest Paid. Are there other comparisons we can draw from the datasets?

---

**Grantmaking Comparison**

Compare council grantmaking in a common format: recipient, amount, purpose, geography and year. An MVP could answer simple questions such as which councils fund similar causes, how grant portfolios change over time and where comparable organisations receive very different support.

---

**What Does It Cost Elsewhere?**  
Compare prices councils pay for comparable goods or services using contract and procurement data. Even a narrow category could reveal useful outliers and show whether cross-council benchmarking can identify potential savings or unusually expensive provision.

# 🪶 Table F Constitutuion

# **🪶Table F Constitution**

*Councils are confusing and endless waves of local government reform ensure a rapid pace of change. Can we build tools to keep on top of this transformation and find data about the structure and constitution of councils that can help the public have a better understanding of what our councils are and how they work?*

**Publication Compliance Checker**

Can we detect when councils publish agendas, minutes or supporting papers late \- or fail to publish documents they are expected to make public? This may require some degree of new scraping but it may be possible to make a start by looking at minutes and decisions and seeing if they align.

---

**Local Government Reorganisation Tracker**

There is constant Local Government Reorganisation. Can we track proposed and confirmed changes to council structures, boundaries, combined authorities and mayoral arrangements coming in the future. Build a clear timeline/map showing what is changing, when, and which existing authorities are affected. This is probably a challenge that requires looking outside the pre scraped datasets but having a single roadmap will make it much easier to keep the things we build today functioning as it will allow us to plan for changes coming down the pipeline in terms of scraping

---

**Constitution Changes Tracker**

We have not yet built scrapers to retrieve the details of constitutions and this is a challenge in the data collection table but there is a second challenge which is keeping track of changes and proposed changes to council structure and infrastructure. Can we build a tool that monitors minutes for discussions around constitutions to help us monitor proposed and actual changes.

# ⚠️ Data Issues & Suggestions

# **⚠️ Data issues and suggestions**

Things other people working today might want to know that you’ve found out about the data, or things that should be cleaned up later.

**TEMPLATE \- COPY THIS AND FILL IN:**  
---

### **Issue**

### **Reported by**

### **Also seen by**

---

[image1]: <data:image/png;base64,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>