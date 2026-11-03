// Phase 1 Interview Studio — static UI copy (categories, difficulties, topics). No fabricated data.
import { Braces, Building2, MessagesSquare, FolderGit2, Shuffle } from 'lucide-react'

export const CATEGORIES = [
  { id: 'technical', label: 'Technical', blurb: 'DSA, SQL and CS fundamentals.', icon: Braces },
  { id: 'hr', label: 'HR', blurb: 'Motivation, fit and self-awareness.', icon: Building2 },
  { id: 'behavioral', label: 'Behavioral', blurb: 'STAR-style situational questions.', icon: MessagesSquare },
  { id: 'project', label: 'Project-Based', blurb: 'Walk through your own work.', icon: FolderGit2 },
  { id: 'mixed', label: 'Mixed', blurb: 'A realistic blend of everything.', icon: Shuffle },
]

export const DIFFICULTIES = [
  { id: 'beginner', label: 'Beginner' },
  { id: 'intermediate', label: 'Intermediate' },
  { id: 'advanced', label: 'Advanced' },
]

export const EXPERIENCE = [
  { id: 'student', label: 'Student / fresher' },
  { id: '0-1', label: '0–1 years' },
  { id: '1-3', label: '1–3 years' },
  { id: '3plus', label: '3+ years' },
]

// Technical topics available as a filter (mirror of the backend question bank topics).
export const TECH_TOPICS = [
  { id: 'complexity', label: 'Time Complexity' },
  { id: 'search', label: 'Binary Search' },
  { id: 'hashing', label: 'Hash Tables' },
  { id: 'recursion', label: 'Recursion' },
  { id: 'sql-joins', label: 'SQL Joins' },
  { id: 'sql-index', label: 'Database Indexes' },
  { id: 'python', label: 'Python Pitfalls' },
]

export const QUESTION_COUNTS = [3, 5, 8, 10]
export const DURATIONS = [10, 20, 30, 45]

export function categoryLabel(id) {
  return CATEGORIES.find((c) => c.id === id)?.label || id
}
