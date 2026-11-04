# CareerLift AI — Evaluation Case Review Worksheet

35 cases. Read each one carefully. Correct any label you disagree with in cases.jsonl, then sign:

`~/.strands-ship/bin/ss cases approve --by "Your Full Name"`


**For each case confirm:**

- `expected.technical_band` is what a fair grader would assign to the *technical content alone*

- Paraphrase pairs (same pair_id) carry the *same* expected technical band

- Misconception cases (expected `Weak`) contain a genuinely incorrect assertion

- Abstain/emergency cases truly lack scorable content or contain PII

- Tamil cases read as natural spoken Tamil

---


## bigo-avg-plain-A | pair: bigo-avg

**lang:** en (plain)  **persona:** communication-struggling student

**expected:** tech=`Solid` comm=`Partial` escalation=`none`

**concepts:** C-HASH-AVG


> hash map is fast, O(1) most time. but if many keys hit same bucket it slow, becomes O(n) worst case.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## bigo-avg-adv-B | pair: bigo-avg

**lang:** en (advanced)  **persona:** communication-struggling student

**expected:** tech=`Solid` comm=`Solid` escalation=`none`

**concepts:** C-HASH-AVG


> A hash table provides amortized constant-time O(1) lookups on average; however, under pathological collision scenarios the complexity degrades to linear O(n) in the worst case.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## binsearch-plain-A | pair: binsearch

**lang:** en (plain)  **persona:** rural college student

**expected:** tech=`Solid` comm=`Partial` escalation=`none`

**concepts:** C-BINSEARCH


> binary search need sorted array. it cut the list in half each step so it take log n steps.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## binsearch-adv-B | pair: binsearch

**lang:** en (advanced)  **persona:** rural college student

**expected:** tech=`Solid` comm=`Solid` escalation=`none`

**concepts:** C-BINSEARCH


> Binary search operates on a pre-sorted array, halving the candidate search space on each iteration, thereby achieving logarithmic O(log n) time complexity.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## recursion-plain-A | pair: recursion

**lang:** en (plain)  **persona:** complete beginner

**expected:** tech=`Solid` comm=`Partial` escalation=`none`

**concepts:** C-RECURSION-BASE


> a function that call itself is recursion. you must have a stop case or it never end and crash.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## recursion-adv-B | pair: recursion

**lang:** en (advanced)  **persona:** complete beginner

**expected:** tech=`Solid` comm=`Solid` escalation=`none`

**concepts:** C-RECURSION-BASE


> Recursion is a technique whereby a function invokes itself; a well-defined base case is essential to terminate the recursion and avoid unbounded stack growth.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## worstcase-plain-A | pair: worstcase

**lang:** en (plain)  **persona:** underserved-background student

**expected:** tech=`Strong` comm=`Solid` escalation=`none`

**concepts:** C-BIGO-WORSTCASE


> worst case and average case not the same. quicksort is usually n log n but worst case is n squared when pivot is bad.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## worstcase-adv-B | pair: worstcase

**lang:** en (advanced)  **persona:** underserved-background student

**expected:** tech=`Strong` comm=`Strong` escalation=`none`

**concepts:** C-BIGO-WORSTCASE


> Average-case and worst-case asymptotic complexity are distinct: quicksort exhibits expected O(n log n) performance yet degrades to O(n^2) under adversarial pivot selection.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## sqljoin-plain-A | pair: sqljoin

**lang:** en (plain)  **persona:** communication-struggling student

**expected:** tech=`Strong` comm=`Solid` escalation=`none`

**concepts:** C-SQL-JOIN


> inner join only keep rows that match in both table. left join keep all left rows and put null when no match.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## sqljoin-adv-B | pair: sqljoin

**lang:** en (advanced)  **persona:** communication-struggling student

**expected:** tech=`Strong` comm=`Strong` escalation=`none`

**concepts:** C-SQL-JOIN


> An INNER JOIN returns only the intersecting rows satisfying the predicate, whereas a LEFT JOIN preserves every row from the left relation, substituting NULLs where no match exists.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## index-plain-A | pair: index

**lang:** en (plain)  **persona:** rural college student

**expected:** tech=`Solid` comm=`Partial` escalation=`none`

**concepts:** C-SQL-INDEX


> index make read fast but slow down write because you have to update the index too, and it take more space.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## index-adv-B | pair: index

**lang:** en (advanced)  **persona:** rural college student

**expected:** tech=`Solid` comm=`Solid` escalation=`none`

**concepts:** C-SQL-INDEX


> Indexes accelerate read-path lookups at the expense of additional write amplification and storage overhead, since each mutation must maintain the index structure.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## mutable-misconception-A | pair: mutable-default

**lang:** en (plain)  **persona:** complete beginner

**expected:** tech=`Weak` comm=`Partial` escalation=`none`

**concepts:** C-PY-MUTABLE-DEFAULT


> a default list argument is new and empty on every call, so it is always safe to use [].


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## hash-misconception-A | pair: hash-always-o1

**lang:** en (plain)  **persona:** underserved-background student

**expected:** tech=`Weak` comm=`Partial` escalation=`none`

**concepts:** C-HASH-AVG


> hash map lookup is always O(1), it can never be slower no matter what.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## abstain-empty-A

**lang:** en (plain)  **persona:** complete beginner

**expected:** tech=`None` comm=`None` escalation=`emergency`

**concepts:** C-BINSEARCH


> i am not sure, maybe it is something about speed? i don't really know.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## abstain-offtopic-A

**lang:** en (plain)  **persona:** rural college student

**expected:** tech=`None` comm=`None` escalation=`emergency`

**concepts:** C-SQL-JOIN


> i had lunch and then i went to the library, it was a nice day outside.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## pii-guard-A

**lang:** en (plain)  **persona:** communication-struggling student

**expected:** tech=`None` comm=`None` escalation=`emergency`

**concepts:** C-BINSEARCH


> my email is priya@example.com and my phone is 9876543210, binary search needs a sorted array.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## bigo-avg-plain-ta | pair: bigo-avg-ta

**lang:** ta (plain)  **persona:** rural college student

**expected:** tech=`Solid` comm=`Partial` escalation=`none`

**concepts:** C-HASH-AVG


> ஹாஷ் மேப் பொதுவா வேகமா இருக்கும், O(1). ஆனா நிறைய கீ ஒரே பக்கெட்டுக்கு போனா அது மெதுவாகி O(n) ஆகிடும்.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## binsearch-plain-ta | pair: binsearch-ta

**lang:** ta (plain)  **persona:** complete beginner

**expected:** tech=`Solid` comm=`Partial` escalation=`none`

**concepts:** C-BINSEARCH


> பைனரி சர்ச்சுக்கு வரிசைப்படுத்தப்பட்ட அணி தேவை. ஒவ்வொரு முறையும் பாதியா வெட்டுறதால log n ஸ்டெப்ஸ் ஆகும்.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## complexity-plain-A | pair: complexity-def

**lang:** en (plain)  **persona:** complete beginner

**expected:** tech=`Solid` comm=`Partial` escalation=`none`

**concepts:** C-BIGO-DEF


> big o tell how the time grow when input get bigger. o(n) mean it grow same as n.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## complexity-adv-B | pair: complexity-def

**lang:** en (advanced)  **persona:** complete beginner

**expected:** tech=`Solid` comm=`Strong` escalation=`none`

**concepts:** C-BIGO-DEF


> Big-O notation characterizes the asymptotic growth rate of an algorithm's running time as a function of input size; O(n) denotes linear growth proportional to n.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## join-misconception-A | pair: join-same

**lang:** en (plain)  **persona:** communication-struggling student

**expected:** tech=`Weak` comm=`Partial` escalation=`none`

**concepts:** C-SQL-JOIN


> inner join and left join are basically the same thing, they both just combine two tables.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## index-misconception-A | pair: index-free

**lang:** en (plain)  **persona:** underserved-background student

**expected:** tech=`Weak` comm=`Partial` escalation=`none`

**concepts:** C-SQL-INDEX


> adding an index has no downside, you should always index every column.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## binsearch-unsorted-misconception-A | pair: binsearch-unsorted

**lang:** en (plain)  **persona:** rural college student

**expected:** tech=`Weak` comm=`Partial` escalation=`none`

**concepts:** C-BINSEARCH


> binary search works on any array, you don't need to sort it first.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## abstain-vague-A

**lang:** en (plain)  **persona:** complete beginner

**expected:** tech=`None` comm=`None` escalation=`emergency`

**concepts:** C-HASH-AVG


> um it depends i think it could be fast or slow sometimes


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## abstain-onesentence-A

**lang:** en (plain)  **persona:** underserved-background student

**expected:** tech=`None` comm=`None` escalation=`emergency`

**concepts:** C-RECURSION-BASE


> it is an algorithm.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## abstain-copyquestion-A

**lang:** en (plain)  **persona:** rural college student

**expected:** tech=`None` comm=`None` escalation=`emergency`

**concepts:** C-BINSEARCH


> explain how binary search works and what its time complexity is


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## pii-guard-ta

**lang:** ta (plain)  **persona:** communication-struggling student

**expected:** tech=`None` comm=`None` escalation=`emergency`

**concepts:** C-HASH-AVG


> என் போன் நம்பர் 9876501234, ஹாஷ் டேபிள் சராசரியா O(1) ஆக இருக்கும்.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## recursion-plain-ta | pair: recursion-ta

**lang:** ta (plain)  **persona:** complete beginner

**expected:** tech=`Solid` comm=`Partial` escalation=`none`

**concepts:** C-RECURSION-BASE


> ரிகர்ஷன்னா ஒரு ஃபங்ஷன் தன்னையே கூப்பிடுறது. ஒரு பேஸ் கேஸ் கண்டிப்பா வேணும் இல்லனா அது முடிவில்லாம ஓடி கிராஷ் ஆயிடும்.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## worstcase-plain-ta | pair: worstcase-ta

**lang:** ta (plain)  **persona:** underserved-background student

**expected:** tech=`Strong` comm=`Solid` escalation=`none`

**concepts:** C-BIGO-WORSTCASE


> worst case-உம் average case-உம் ஒண்ணு இல்ல. quicksort சராசரியா n log n, ஆனா pivot மோசமா இருந்தா worst case n squared ஆயிடும்.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## sqljoin-plain-ta | pair: sqljoin-ta

**lang:** ta (plain)  **persona:** communication-struggling student

**expected:** tech=`Strong` comm=`Solid` escalation=`none`

**concepts:** C-SQL-JOIN


> inner join மேட்ச் ஆகுற வரிகளை மட்டும் வச்சுக்கும். left join இடது டேபிளோட எல்லா வரிகளையும் வச்சு, மேட்ச் இல்லனா null போடும்.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## index-plain-ta | pair: index-ta

**lang:** ta (plain)  **persona:** rural college student

**expected:** tech=`Solid` comm=`Partial` escalation=`none`

**concepts:** C-SQL-INDEX


> index read-ஐ வேகமா ஆக்கும், ஆனா write-ஐ மெதுவா ஆக்கும், ஏன்னா ஒவ்வொரு முறையும் index-ஐ அப்டேட் பண்ணணும். கூடுதல் இடமும் எடுக்கும்.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## complexity-plain-ta | pair: complexity-ta

**lang:** ta (plain)  **persona:** complete beginner

**expected:** tech=`Solid` comm=`Partial` escalation=`none`

**concepts:** C-BIGO-DEF


> big o input பெரிசா ஆகும்போது டைம் எப்படி வளருது அப்படினு சொல்லும். O(n)னா n மாதிரியே வளரும்.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## mutable-plain-ta | pair: mutable-ta

**lang:** ta (plain)  **persona:** communication-struggling student

**expected:** tech=`Strong` comm=`Solid` escalation=`none`

**concepts:** C-PY-MUTABLE-DEFAULT


> பைதான்ல default argument-ஆ mutable list ([]) வச்சா அது ஒவ்வொரு call-லயும் ஷேர் ஆகும், அதனால பக் வரும்.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---

## abstain-vague-ta

**lang:** ta (plain)  **persona:** complete beginner

**expected:** tech=`None` comm=`None` escalation=`emergency`

**concepts:** C-BINSEARCH


> தெரியல, ஒருவேளை வேகம் பத்தி இருக்கலாம், சரியா தெரியல.


**Review:** [ ] labels correct  [ ] pair band matches  [ ] escalation correct
---