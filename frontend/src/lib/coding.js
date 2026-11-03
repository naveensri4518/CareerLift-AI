// Phase 2 Coding Arena — static UI copy + verdict/difficulty mapping. No fabricated data: all counts,
// verdicts and timings shown in the UI come straight from the backend evaluation payload.

// Difficulty -> label + accent colour (reuses the four-accent system).
export const DIFFICULTY_META = {
  beginner: { label: 'Beginner', tone: 'green', hex: '#22c55e' },
  intermediate: { label: 'Intermediate', tone: 'orange', hex: '#f97316' },
  advanced: { label: 'Advanced', tone: 'bad', hex: '#f87171' },
}

export function difficultyMeta(id) {
  return DIFFICULTY_META[id] || { label: id, tone: 'muted', hex: '#64748b' }
}

export const DIFFICULTY_ORDER = ['beginner', 'intermediate', 'advanced']

// Verdict -> label, tone (for Badge), colour and whether it's the success state.
export const VERDICT_META = {
  ACCEPTED: { label: 'Accepted', tone: 'good', hex: '#34d399', ok: true },
  'WRONG ANSWER': { label: 'Wrong Answer', tone: 'bad', hex: '#f87171', ok: false },
  'COMPILATION ERROR': { label: 'Compilation Error', tone: 'warn', hex: '#fbbf24', ok: false },
  'TIME LIMIT EXCEEDED': { label: 'Time Limit Exceeded', tone: 'warn', hex: '#fbbf24', ok: false },
  'RUNTIME ERROR': { label: 'Runtime Error', tone: 'bad', hex: '#f87171', ok: false },
}

export function verdictMeta(v) {
  return VERDICT_META[v] || { label: v || 'Pending', tone: 'muted', hex: '#64748b', ok: false }
}

// Default starter code per language so the editor is never empty.
export const STARTER = {
  python: `import sys

def main():
    data = sys.stdin.read().split()
    # TODO: solve the problem and print the answer
    print()

main()
`,
  cpp: `#include <bits/stdc++.h>
using namespace std;

int main() {
    // TODO: read from stdin, print the answer to stdout
    return 0;
}
`,
  java: `import java.util.*;
import java.io.*;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        // TODO: read from stdin, print the answer to stdout
    }
}
`,
}

export function languageLabel(id) {
  return { python: 'Python 3', cpp: 'C++17', java: 'Java 17' }[id] || id
}
