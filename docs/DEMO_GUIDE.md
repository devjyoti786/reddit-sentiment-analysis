# Demonstration and explanation guide

**Project:** Reddit Stock Sentiment Analyzer by Devjyoti

## Run the demonstration

From the repository folder, after completing the [README setup](../README.md):

```bash
source .venv/bin/activate
python main.py --demo
python -m pytest -q
```

On Windows, activate with `.venv\Scripts\activate`. The demo does not require
Reddit credentials. VADER's first run may need internet access for its lexicon.

Open the output folder printed by the program. Show `mentions.csv`, `sentiment.csv`,
the two PNG charts and `run.json`. The source comments are in `comments.jsonl`.

To demonstrate replay, replace the example path with your actual run folder:

```bash
python main.py --input output/YOUR_RUN_FOLDER/comments.jsonl
```

## A short presentation sequence

1. **Explain the purpose:** turn stock-discussion comments into contributor counts
   and language-tone summaries. State that the demonstration comments are synthetic.
2. **Show one input:** `GME to the moon! Holding my calls.` The ticker identifies
   the subject; only the sentence explicitly mentioning GME is used for its score.
3. **Explain fair counting:** one named author counts once per ticker. Their relevant
   comment scores are averaged before the ticker summary is calculated.
4. **Show the output:** GME, PLTR and TSLA each have three contributors in the sample.
   Alphabetical ordering resolves the tie. Explain a mean score and a sentiment share.
5. **Show reliability:** point to passing tests, unique run folders and saved metadata.
6. **Close with limitations and attribution:** discuss sarcasm and shared sentences,
   and identify the upstream project and this version's extensions.

## Questions to practise

**What does VADER do?**  
It uses a sentiment vocabulary and rules, including negation and emphasis, to score
text. This project adds some stock-discussion words; it does not train a model.

**What is the difference between a mention and a comment?**  
Here, a mention means a contributor discussing a ticker. One author can write many
comments but still contribute one mention and one averaged sentiment score.

**Why remove URLs and mask tickers?**  
A symbol inside a link can be an accidental match. A ticker such as `$LOVE` can also
be mistaken for an emotional word. These two steps reduce those errors.

**Does a positive score predict a price increase?**  
No. It describes the language tone recognised by the rules, not investment outcomes.

**How accurate is it?**  
Accuracy has not been measured on labelled real comments. Automated tests check
software behaviour. A separate labelled dataset is needed for an accuracy evaluation.

**What happens when collection fails?**  
Comments already written remain in the run folder, and metadata records the failure.
They can be replayed, but replay cannot recover comments that were never collected.

**Which parts were extended?**  
The [project report](PROJECT_REPORT.md) identifies the added features and credits the
original MIT-licensed project. Use that distinction when explaining the work.
