import { useEffect, useState, useRef } from 'react'
import {
  BookOpen,
  Bookmark,
  Flag,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  FileText,
  LayoutGrid,
  Save,
  Search,
  Send,
  Pencil,
Trash2,
X,
Check,
  Shuffle,
  User,
  History as HistoryIcon,
  Settings,
} from 'lucide-react'
import './App.css'
import './Quiz.css'
import './PageSwitch.css'
import './Learner.css'
import './QuestionDetail.css'
import './Practice.css'
import './Bookmarks.css'
import './History.css'
import './AccountReview.css'

const PAGE_SIZE = 12

const formatNoteDate = (value) => {
  if (!value) return ''

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return ''
  }

  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

const paperOptions = {
  all: ['all'],
  prelims: ['all', 'Prelims GS', 'Prelims CSAT'],
  mains: ['all', 'gs1', 'gs2', 'gs3', 'gs4', 'essay', 'sociology1', 'sociology2'],
}

function App() {
  const [questions, setQuestions] = useState([])
  const [stage, setStage] = useState('prelims')
  const [paper, setPaper] = useState('all')
  const [year, setYear] = useState('all')
  const [query, setQuery] = useState('')
  const [pagination, setPagination] = useState({
    page: 1,
    pages: 1,
    total: 0,
  })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [hierarchy, setHierarchy] = useState([])
  const [view, setView] = useState(
    () => (window.location.hash === '#practice' ? 'questions' : 'syllabus')
  )
  const [node, setNode] = useState('')
  const [attemptId, setAttemptId] = useState(null)
  const [responses, setResponses] = useState({})
  const [notes, setNotes] = useState({})
const [noteDrafts, setNoteDrafts] = useState({})
  const [bookmarks, setBookmarks] = useState([])
  const [reviewQuestions, setReviewQuestions] = useState([])
  const [reviews, setReviews] = useState([])
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewFilter, setReviewFilter] = useState('all')
  const [selectedReview, setSelectedReview] = useState(null)
  const [reviewReasons, setReviewReasons] = useState([])
  const [reviewNote, setReviewNote] = useState('')
  const [profileEditing, setProfileEditing] = useState(false)
  const [profileDraft, setProfileDraft] = useState({})
  const [goals, setGoals] = useState([])
  const [goalEditing, setGoalEditing] = useState(null)
  const [feedback, setFeedback] = useState({})
  const [profileData, setProfileData] = useState(null)
  const [historyItems, setHistoryItems] = useState([])
  const [bookmarkItems, setBookmarkItems] = useState([])
  const [quizQuestion, setQuizQuestion] = useState(null)
  const [quizLoading, setQuizLoading] = useState(false)
  const [quizSubmitting, setQuizSubmitting] = useState(false)
  const [quizAttachment, setQuizAttachment] = useState(null)
  const [quizStageFilter, setQuizStageFilter] = useState('all')
  const [practiceSubject, setPracticeSubject] = useState('all')

  // Dedicated question-page state
  const [detailQuestion, setDetailQuestion] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [detailAnswer, setDetailAnswer] = useState('')
  const [detailSubmitting, setDetailSubmitting] = useState(false)
  const [detailFeedback, setDetailFeedback] = useState(null)
  const [detailAttempted, setDetailAttempted] = useState(false)
  const [detailAttempts, setDetailAttempts] = useState([])
const [detailNotes, setDetailNotes] = useState([])
const [detailNoteDraft, setDetailNoteDraft] = useState('')
const [editingNoteId, setEditingNoteId] = useState(null)
const [editingNoteText, setEditingNoteText] = useState('')
const [noteActionLoading, setNoteActionLoading] = useState(false)

  // Toast notification
  const [notification, setNotification] = useState({
    message: '',
    type: '',
  })
  const notificationTimer = useRef(null)

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type })

    if (notificationTimer.current) {
      clearTimeout(notificationTimer.current)
    }

    notificationTimer.current = setTimeout(() => {
      setNotification({ message: '', type: '' })
    }, 3500)
  }

  useEffect(() => {
    fetch('/api/syllabus/hierarchy/')
      .then((response) =>
        response.ok ? response.json() : Promise.reject()
      )
      .then((data) => setHierarchy(data.papers))
      .catch(() => setError(true))
  }, [])

  const loadProfile = () =>
  fetch('/api/learners/me/')
    .then((response) =>
      response.ok ? response.json() : Promise.reject()
    )
    .then((data) => {
      setProfileData(data)
      setBookmarks(data.bookmarks || [])

      // The profile API now returns:
      //
      // notes: {
      //   "question-id": [
      //      { id, note, created_at, updated_at },
      //      ...
      //   ]
      // }
      //
      // The question-list view only needs the latest note text.
      const latestNotes = {}

      Object.entries(data.notes || {}).forEach(
        ([questionKey, questionNotes]) => {
          if (Array.isArray(questionNotes)) {
            const latest = questionNotes[0]

            if (latest && typeof latest === 'object') {
              latestNotes[questionKey] = latest.note || ''
            } else if (typeof latest === 'string') {
              latestNotes[questionKey] = latest
            }
          } else if (typeof questionNotes === 'string') {
            // Backward compatibility with old API response
            latestNotes[questionKey] = questionNotes
          }
        }
      )

      setNotes(latestNotes)
    })
    .catch(() => undefined)


  const loadHistory = () => {
    fetch('/api/history/')
      .then((response) =>
        response.ok ? response.json() : Promise.reject()
      )
      .then((data) => {
        const seen = new Set()
        const unique = (data.history || []).filter((item) => {
          if (seen.has(item.question_key)) return false
          seen.add(item.question_key)
          return true
        })
        setHistoryItems(unique)
      })
      .catch(() => setHistoryItems([]))
  }

  const loadBookmarks = () => {
    fetch('/api/bookmarks/')
      .then((response) =>
        response.ok ? response.json() : Promise.reject()
      )
      .then((data) => setBookmarkItems(data.bookmarks || []))
      .catch(() => setBookmarkItems([]))
  }

  const loadRandomQuizQuestion = async (requestedStage) => {
    // React passes a MouseEvent when this function is used directly as an
    // onClick handler. Never let that event become "[object Object]" in the
    // API query string. Only accept the three supported quiz stages.
    const stage =
      typeof requestedStage === 'string' &&
      ['all', 'prelims', 'mains'].includes(requestedStage.toLowerCase())
        ? requestedStage.toLowerCase()
        : quizStageFilter

    setQuizLoading(true)

    try {
      // Primary endpoint. The Django URL must be registered before
      // /api/questions/<question_key>/ so 'random' is not treated as a key.
      // Quiz supports both Prelims and Mains. Prelims gets instant correctness;
      // Mains can be submitted directly here with an answer-sheet upload.
      let response = await fetch(`/api/questions/random/?stage=${stage}`, {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
        cache: 'no-store',
      })

      let data = {}
      try {
        data = await response.json()
      } catch {
        data = {}
      }

      if (!response.ok) {
        throw new Error(
          data.error || data.message || `Failed to load quiz (${response.status})`
        )
      }

      const question = data.question || null
      setQuizQuestion(question)
      setResponses((current) => {
        if (!question?.id) return current
        const next = { ...current }
        delete next[question.id]
        return next
      })
      setFeedback((current) => {
        if (!question?.id) return current
        const next = { ...current }
        delete next[question.id]
        return next
      })
      setQuizSubmitting(false)
      setQuizAttachment(null)
      if (question?.id) {
        setDetailQuestion(null)
      }
    } catch (error) {
      console.error('Failed to load random quiz question:', error)
      setQuizQuestion(null)
      showNotification(
        error.message || 'Could not load a random question',
        'error'
      )
    } finally {
      setQuizLoading(false)
    }
  }


  // Quiz answers are submitted directly from the quiz page. The quiz can
  // contain both Prelims and Mains questions.
  const submitQuizAnswer = async (attachment = null) => {
    if (!quizQuestion || quizSubmitting) return

    const quizStage = String(quizQuestion.id || '').startsWith('mains-')
      ? 'mains'
      : 'prelims'
    const isPrelims = quizStage === 'prelims'
    const selectedAnswer = responses[quizQuestion.id]

    if (isPrelims && !selectedAnswer) {
      showNotification('Please select an answer first', 'error')
      return
    }

    if (!isPrelims && !attachment) {
      showNotification('Please upload your answer sheet first', 'error')
      return
    }

    setQuizSubmitting(true)

    try {
      const attemptResponse = await fetch('/api/attempts/start/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          stage: quizStage,
          paper: quizQuestion.paper,
          node_id: quizQuestion.topic_id || quizQuestion.subject_id || '',
          total_questions: 1,
        }),
      })

      const attemptData = await attemptResponse.json().catch(() => ({}))
      if (!attemptResponse.ok || !attemptData.id) {
        throw new Error(
          attemptData.error ||
            attemptData.message ||
            `Failed to start quiz attempt (${attemptResponse.status})`
        )
      }

      let response

      if (isPrelims) {
        response = await fetch(
          `/api/attempts/${attemptData.id}/responses/`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            credentials: 'same-origin',
            body: JSON.stringify({
              question_key: quizQuestion.id,
              question_stage: 'prelims',
              selected_answer: selectedAnswer,
              node_id: quizQuestion.topic_id || quizQuestion.subject_id || '',
              node_type: quizQuestion.topic_id ? 'topic' : 'subject',
            }),
          }
        )
      } else {
        const form = new FormData()
        form.append('question_key', quizQuestion.id)
        form.append('question_stage', 'mains')
        form.append('node_id', quizQuestion.topic_id || quizQuestion.subject_id || '')
        form.append('node_type', quizQuestion.topic_id ? 'topic' : 'subject')
        form.append('attachment', attachment)

        response = await fetch(
          `/api/attempts/${attemptData.id}/responses/`,
          {
            method: 'POST',
            body: form,
            credentials: 'same-origin',
          }
        )
      }

      const result = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(
          result.error ||
            result.message ||
            `Failed to submit answer (${response.status})`
        )
      }

      const submitResponse = await fetch(
        `/api/attempts/${attemptData.id}/submit/`,
        {
          method: 'POST',
          credentials: 'same-origin',
        }
      )

      const submitData = await submitResponse.json().catch(() => ({}))
      if (!submitResponse.ok) {
        throw new Error(
          submitData.error ||
            submitData.message ||
            `Failed to complete quiz attempt (${submitResponse.status})`
        )
      }

      setResponses((current) => ({
        ...current,
        ...(isPrelims ? { [quizQuestion.id]: selectedAnswer } : {}),
      }))
      setFeedback((current) => ({
        ...current,
        [quizQuestion.id]: isPrelims
          ? result
          : { ...result, mains_submitted: true },
      }))
      setQuizAttachment(null)

      loadHistory()
      loadProfile()

      showNotification(
        isPrelims
          ? result.is_correct
            ? 'Correct answer!'
            : 'Incorrect answer'
          : 'Answer sheet submitted successfully',
        isPrelims && !result.is_correct ? 'error' : 'success'
      )
    } catch (error) {
      console.error('Failed to submit quiz answer:', error)
      showNotification(error.message || 'Failed to submit answer', 'error')
    } finally {
      setQuizSubmitting(false)
    }
  }

  const ensureAttempt = () => {
    if (attemptId) {
      return Promise.resolve(attemptId)
    }

    return fetch('/api/attempts/start/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        stage,
        paper,
        node_id: node,
        total_questions: pagination.total,
      }),
    })
      .then(async (response) => {
        let data = {}
        try {
          data = await response.json()
        } catch {
          data = {}
        }

        if (!response.ok) {
          throw new Error(
            data.error ||
              data.message ||
              `Failed to start attempt (${response.status})`
          )
        }

        if (!data.id) {
          throw new Error(
            'Attempt was created but no attempt ID was returned.'
          )
        }

        return data
      })
      .then((data) => {
        setAttemptId(data.id)
        showNotification('Attempt started successfully', 'success')
        return data.id
      })
      .catch((error) => {
        console.error('Failed to start attempt:', error)
        showNotification(
          error.message || 'Failed to start attempt',
          'error'
        )
        throw error
      })
  }

  const saveResponse = (item, value, attachment = null) => {
    return ensureAttempt().then((id) => {
      if (item.stage === 'mains') {
        const form = new FormData()
        form.append('question_key', item.id)
        form.append('question_stage', item.stage)
        if (attachment) {
          form.append('attachment', attachment)
        }
        return fetch(`/api/attempts/${id}/responses/`, {
          method: 'POST',
          body: form,
        })
      }

      return fetch(`/api/attempts/${id}/responses/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question_key: item.id,
          question_stage: item.stage,
          selected_answer: value,
        }),
      })
    })
      .then(async (response) => {
        let result = {}
        try {
          result = await response.json()
        } catch {
          result = {}
        }

        if (!response.ok) {
          throw new Error(
            result.error ||
              result.message ||
              `Failed to save response (${response.status})`
          )
        }

        return result
      })
      .then((result) => {
        setResponses((current) => ({
          ...current,
          [item.id]: value,
        }))

        if (item.stage === 'prelims') {
          setFeedback((current) => ({
            ...current,
            [item.id]: result,
          }))
        }

        if (item.stage === 'prelims') {
          if (result.is_correct) {
            showNotification('Answer submitted — Correct!', 'success')
          } else {
            showNotification('Answer submitted — Wrong answer', 'error')
          }
        } else {
          showNotification('Answer submitted successfully', 'success')
        }

        return result
      })
      .catch((error) => {
        console.error('Failed to save response:', error)
        showNotification(
          error.message || 'Failed to save response',
          'error'
        )
        throw error
      })
  }

  const toggleBookmark = (questionKey) => {
    const bookmarked = bookmarks.includes(questionKey)

    fetch(`/api/questions/${questionKey}/bookmark/`, {
      method: bookmarked ? 'DELETE' : 'POST',
    })
      .then(async (response) => {
        if (!response.ok) {
          let data = {}
          try {
            data = await response.json()
          } catch {
            data = {}
          }
          throw new Error(
            data.error ||
              data.message ||
              `Failed to update bookmark (${response.status})`
          )
        }
        return response
      })
      .then(() => {
        setBookmarks((current) =>
          bookmarked
            ? current.filter((item) => item !== questionKey)
            : [...current, questionKey]
        )
        showNotification(
          bookmarked ? 'Bookmark removed' : 'Question bookmarked',
          'success'
        )
      })
      .catch((error) => {
        console.error('Failed to update bookmark:', error)
        showNotification(
          error.message || 'Failed to update bookmark',
          'error'
        )
      })
  }

  const loadReviews = (filter = reviewFilter) => {
    setReviewLoading(true)
    const query = filter === 'all' ? 'status=all' : `status=${filter}`
    fetch(`/api/reviews/?${query}`, { credentials: 'same-origin', cache: 'no-store' })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(data.error || 'Failed to load reviews')
        return data
      })
      .then((data) => {
        setReviews(Array.isArray(data.reviews) ? data.reviews : [])
        setReviewQuestions((data.reviews || []).filter((r) => r.status === 'open').map((r) => r.question_key))
      })
      .catch((error) => showNotification(error.message || 'Failed to load reviews', 'error'))
      .finally(() => setReviewLoading(false))
  }

  const saveReview = async (questionKey, reasons = reviewReasons, note = reviewNote) => {
    if (!questionKey) return
    try {
      const response = await fetch(`/api/questions/${encodeURIComponent(questionKey)}/review/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reasons, note }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.error || 'Failed to save review')
      const saved = data.review
      setReviewQuestions((current) => current.includes(questionKey) ? current : [...current, questionKey])
      setReviews((current) => [saved, ...current.filter((item) => item.id !== saved.id)])
      if (selectedReview?.id === saved.id) setSelectedReview(saved)
      showNotification('Review saved', 'success')
      return saved
    } catch (error) {
      showNotification(error.message || 'Failed to save review', 'error')
      throw error
    }
  }

  const toggleReviewQuestion = (questionKey) => {
    if (!questionKey) return
    const marked = reviewQuestions.includes(questionKey)
    if (marked) {
      fetch(`/api/questions/${encodeURIComponent(questionKey)}/review/`, { method: 'DELETE' })
        .then(async (response) => {
          const data = await response.json().catch(() => ({}))
          if (!response.ok) throw new Error(data.error || 'Failed to remove review')
          setReviewQuestions((current) => current.filter((item) => item !== questionKey))
          setReviews((current) => current.filter((item) => item.question_key !== questionKey))
          showNotification('Removed from review', 'success')
        })
        .catch((error) => showNotification(error.message || 'Failed to remove review', 'error'))
      return
    }
    setReviewReasons([])
    setReviewNote('')
    saveReview(questionKey, [], '')
  }

  const openReviewEditor = (review) => {
    setSelectedReview(review)
    setReviewReasons(Array.isArray(review.reasons) ? review.reasons : [])
    setReviewNote(review.note || '')
  }

  const updateSelectedReview = async () => {
    if (!selectedReview) return
    try {
      const response = await fetch(`/api/reviews/${selectedReview.id}/`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reasons: reviewReasons, note: reviewNote }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.error || 'Failed to update review')
      setSelectedReview(data.review)
      setReviews((current) => current.map((item) => item.id === data.review.id ? data.review : item))
      showNotification('Review updated', 'success')
    } catch (error) { showNotification(error.message || 'Failed to update review', 'error') }
  }

  const resolveReview = async (reviewId) => {
    try {
      const response = await fetch(`/api/reviews/${reviewId}/resolve/`, { method: 'POST' })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.error || 'Failed to resolve review')
      setReviews((current) => current.map((item) => item.id === reviewId ? data.review : item))
      setReviewQuestions((current) => current.filter((key) => key !== data.review.question_key))
      setSelectedReview(data.review)
      showNotification('Review resolved', 'success')
    } catch (error) { showNotification(error.message || 'Failed to resolve review', 'error') }
  }

  const loadGoals = () => {
    fetch('/api/goals/', { credentials: 'same-origin', cache: 'no-store' })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => setGoals(data.goals || []))
      .catch(() => setGoals([]))
  }

  const startProfileEdit = () => {
    const learner = profileData?.learner || {}
    setProfileDraft({ ...learner })
    setProfileEditing(true)
  }

  const saveProfile = async () => {
    try {
      const response = await fetch('/api/learners/me/', {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profileDraft),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.error || 'Failed to save profile')
      setProfileData(data)
      setProfileEditing(false)
      showNotification('Profile updated', 'success')
    } catch (error) { showNotification(error.message || 'Failed to save profile', 'error') }
  }

  const saveGoal = async (draft) => {
    const isEdit = Boolean(goalEditing?.id)
    try {
      const response = await fetch(isEdit ? `/api/goals/${goalEditing.id}/` : '/api/goals/', {
        method: isEdit ? 'PATCH' : 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.error || 'Failed to save goal')
      const saved = data.goal
      setGoals((current) => isEdit ? current.map((g) => g.id === saved.id ? saved : g) : [...current, saved])
      setGoalEditing(null)
      showNotification('Goal saved', 'success')
    } catch (error) { showNotification(error.message || 'Failed to save goal', 'error') }
  }

  const deleteGoal = async (goalId) => {
    if (!window.confirm('Delete this goal?')) return
    const response = await fetch(`/api/goals/${goalId}/`, { method: 'DELETE' })
    if (response.ok) { setGoals((current) => current.filter((g) => g.id !== goalId)); showNotification('Goal deleted', 'success') }
    else showNotification('Failed to delete goal', 'error')
  }

  const ExamCountdown = ({ examDate }) => {
    if (!examDate) return <span className="goal-countdown muted">No exam date</span>
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const exam = new Date(`${examDate}T00:00:00`); const diff = Math.ceil((exam - today) / 86400000)
    if (diff === 0) return <span className="goal-countdown"><strong>Today</strong></span>
    if (diff < 0) return <span className="goal-countdown"><strong>Exam completed</strong></span>
    return <span className="goal-countdown"><strong>{diff}</strong><small>DAYS<br />remaining</small></span>
  }

  const saveNote = (questionKey, note) => {
  const trimmedNote = note.trim()

  if (!trimmedNote) {
    showNotification('Please enter a note first', 'error')
    return
  }

  // Practice-list notes are ALWAYS new notes.
  // Do not use /note/ here because that endpoint is an upsert/update
  // operation and can overwrite the existing private note.
  fetch(`/api/questions/${encodeURIComponent(questionKey)}/notes/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ note: trimmedNote }),
  })
    .then(async (response) => {
      let data = {}

      try {
        data = await response.json()
      } catch {
        data = {}
      }

      if (!response.ok) {
        throw new Error(
          data.error ||
            data.message ||
            `Failed to save note (${response.status})`
        )
      }

      return data
    })
    .then((data) => {
      // Keep the newest note visible on the list. The backend's /notes/
      // endpoint creates a new record instead of updating the old one.
      const createdNote =
        data?.note && typeof data.note === 'object'
          ? data.note.note || trimmedNote
          : typeof data?.note === 'string'
            ? data.note
            : trimmedNote

      setNotes((current) => ({
        ...current,
        [questionKey]: createdNote,
      }))

      setNoteDrafts((current) => ({
        ...current,
        [questionKey]: '',
      }))

      showNotification('Note saved successfully', 'success')
    })
    .catch((error) => {
      console.error('Failed to save note:', error)

      showNotification(
        error.message || 'Failed to save note',
        'error'
      )
    })
}

const isCurrentAffairsRelevant = (value) => {
  if (value === true) return true

  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()

    return [
      'true',
      'yes',
      'relevant',
      'highly relevant',
      'directly relevant',
    ].includes(normalized)
  }

  return false
}

  useEffect(() => {
    const params = new URLSearchParams({
      stage,
      paper,
      year,
      search: query,
      node,
      page,
      page_size: PAGE_SIZE,
    })

    fetch(`/api/questions/?${params}`)
      .then((response) =>
        response.ok ? response.json() : Promise.reject()
      )
      .then((data) => {
        setQuestions(data.questions)
        setPagination(data.pagination)
        setError(false)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [stage, paper, year, query, page, node])

  const getQuestionKeyFromHash = () => {
    const hash = window.location.hash || ''
    if (!hash.startsWith('#question/')) return ''
    return decodeURIComponent(hash.slice('#question/'.length))
  }

  const openQuestion = (questionKey) => {
    window.location.hash = `question/${encodeURIComponent(questionKey)}`
  }

  const navigateQuestion = async (direction) => {
    if (!detailQuestion) return

    const currentIndex = questions.findIndex(
      (question) => question.id === detailQuestion.id
    )

    // Prefer the questions already loaded on the current Practice page.
    if (currentIndex !== -1) {
      const targetIndex = currentIndex + direction

      if (targetIndex >= 0 && targetIndex < questions.length) {
        openQuestion(questions[targetIndex].id)
        return
      }
    }

    // If the user is at the edge of a page, load the adjacent Practice page
    // using the same filters and continue from its first/last question.
    const targetPage = page + direction
    if (targetPage < 1 || targetPage > pagination.pages) return

    try {
      setLoading(true)

      const params = new URLSearchParams({
        stage,
        paper,
        year,
        search: query,
        node,
        page: targetPage,
        page_size: PAGE_SIZE,
      })

      const response = await fetch(`/api/questions/?${params}`)
      if (!response.ok) throw new Error('Failed to load adjacent questions')

      const data = await response.json()
      const adjacentQuestions = Array.isArray(data.questions)
        ? data.questions
        : []

      if (!adjacentQuestions.length) return

      setQuestions(adjacentQuestions)
      setPagination(data.pagination || pagination)
      setPage(targetPage)

      const targetQuestion =
        direction > 0
          ? adjacentQuestions[0]
          : adjacentQuestions[adjacentQuestions.length - 1]

      openQuestion(targetQuestion.id)
    } catch (error) {
      console.error('Failed to navigate between questions:', error)
      showNotification('Could not load the next question', 'error')
    } finally {
      setLoading(false)
    }
  }

  const closeQuestion = () => {
    window.location.hash = 'practice'
  }

  const navigateTo = (nextView) => {
    window.location.hash = nextView
    setView(nextView)
  }

  const loadQuestionDetail = (questionKey) => {
  if (!questionKey) return

  setDetailLoading(true)
  setDetailError('')
  setDetailQuestion(null)
  setDetailFeedback(null)
  setDetailAnswer('')
  setDetailAttempted(false)
  setDetailAttempts([])

  // Important:
  // Clear notes from the previous question before loading this question.
  setDetailNotes([])
  setDetailNoteDraft('')
  setEditingNoteId(null)
  setEditingNoteText('')

  fetch(`/api/questions/${encodeURIComponent(questionKey)}/`)
    .then(async (response) => {
      let data = {}

      try {
        data = await response.json()
      } catch {
        data = {}
      }

      if (!response.ok) {
        throw new Error(
          data.error ||
            data.message ||
            `Failed to load question (${response.status})`
        )
      }

      return data
    })
    .then((data) => {
      const question = data.question

      setDetailQuestion(question)
      setDetailAttempted(Boolean(data.attempted))
      setDetailAttempts(Array.isArray(data.responses) ? data.responses : [])

      /*
       * The backend may return the notes as `notes` or `note`.
       * Normalize both formats into the array expected by the UI.
       */
      const loadedNotes = Array.isArray(data.notes)
        ? data.notes
        : Array.isArray(data.note)
          ? data.note
          : data.note && typeof data.note === 'object'
            ? [data.note]
            : []

      setDetailNotes(loadedNotes)

      setDetailNoteDraft('')

      setDetailAnswer(data.latest_response?.selected_answer || '')

      if (data.latest_result) {
        setDetailFeedback(data.latest_result)
      }
    })
    .catch((error) => {
      console.error('Failed to load question:', error)
      setDetailError(
        error.message || 'Failed to load question'
      )
    })
    .finally(() => {
      setDetailLoading(false)
    })
}

  useEffect(() => {
    const syncRoute = () => {
      const questionKey = getQuestionKeyFromHash()

      if (questionKey) {
        setView('question')
        loadQuestionDetail(questionKey)
        return
      }

      const route = (window.location.hash || '#practice').slice(1)

      if (
        ['syllabus', 'questions', 'practice', 'bookmarks', 'history', 'review', 'quiz', 'account'].includes(route)
      ) {
        setView(route === 'questions' ? 'practice' : route)
        if (route === 'bookmarks') loadBookmarks()
        if (route === 'history') loadHistory()
        if (route === 'quiz') loadRandomQuizQuestion()
        return
      }

      setView('practice')
    }

    syncRoute()
    window.addEventListener('hashchange', syncRoute)
    return () => window.removeEventListener('hashchange', syncRoute)
  }, [])

  const submitDetailAnswer = async (attachment = null) => {
    if (!detailQuestion || detailSubmitting) return

    if (detailQuestion.stage === 'prelims' && !detailAnswer) {
      showNotification('Please select an answer first', 'error')
      return
    }

    setDetailSubmitting(true)

    try {
      const attemptResponse = await fetch('/api/attempts/start/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          stage: detailQuestion.stage,
          paper: detailQuestion.paper,
          node_id: detailQuestion.topic_id || detailQuestion.subject_id || '',
          total_questions: 1,
        }),
      })

      let attemptData = {}
      try {
        attemptData = await attemptResponse.json()
      } catch {
        attemptData = {}
      }

      if (!attemptResponse.ok || !attemptData.id) {
        throw new Error(
          attemptData.error ||
            attemptData.message ||
            `Failed to start attempt (${attemptResponse.status})`
        )
      }

      const attemptIdForQuestion = attemptData.id
      let responseResult = {}

      if (detailQuestion.stage === 'mains') {
        const form = new FormData()
        form.append('question_key', detailQuestion.id)
        form.append('question_stage', 'mains')
        form.append(
          'node_id',
          detailQuestion.topic_id || detailQuestion.subject_id || ''
        )
        form.append(
          'node_type',
          detailQuestion.topic_id ? 'topic' : 'subject'
        )

        if (attachment) {
          form.append('attachment', attachment)
        }

        const response = await fetch(
          `/api/attempts/${attemptIdForQuestion}/responses/`,
          {
            method: 'POST',
            body: form,
          }
        )

        try {
          responseResult = await response.json()
        } catch {
          responseResult = {}
        }

        if (!response.ok) {
          throw new Error(
            responseResult.error ||
              responseResult.message ||
              `Failed to submit answer (${response.status})`
          )
        }
      } else {
        const response = await fetch(
          `/api/attempts/${attemptIdForQuestion}/responses/`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              question_key: detailQuestion.id,
              question_stage: 'prelims',
              selected_answer: detailAnswer,
              node_id:
                detailQuestion.topic_id ||
                detailQuestion.subject_id ||
                '',
              node_type: detailQuestion.topic_id ? 'topic' : 'subject',
            }),
          }
        )

        try {
          responseResult = await response.json()
        } catch {
          responseResult = {}
        }

        if (!response.ok) {
          throw new Error(
            responseResult.error ||
              responseResult.message ||
              `Failed to submit answer (${response.status})`
          )
        }
      }

      const submitResponse = await fetch(
        `/api/attempts/${attemptIdForQuestion}/submit/`,
        {
          method: 'POST',
        }
      )

      let submitData = {}
      try {
        submitData = await submitResponse.json()
      } catch {
        submitData = {}
      }

      if (!submitResponse.ok) {
        throw new Error(
          submitData.error ||
            submitData.message ||
            `Failed to complete attempt (${submitResponse.status})`
        )
      }

      setDetailAttempted(true)

      if (detailQuestion.stage === 'prelims') {
        setDetailFeedback({
          ...responseResult,
          correct_answer:
            responseResult.correct_answer ||
            responseResult.answer ||
            null,
          explanation: responseResult.explanation || '',
          option_explanations:
            responseResult.option_explanations || {},
        })
      }

      showNotification(
        detailQuestion.stage === 'prelims'
          ? responseResult.is_correct
            ? 'Answer submitted — Correct!'
            : 'Answer submitted — Incorrect'
          : 'Answer submitted successfully',
        detailQuestion.stage === 'prelims' && !responseResult.is_correct
          ? 'error'
          : 'success'
      )

      loadQuestionDetail(detailQuestion.id)
    } catch (error) {
      console.error('Failed to submit question:', error)
      showNotification(
        error.message || 'Failed to submit answer',
        'error'
      )
    } finally {
      setDetailSubmitting(false)
    }
  }

const startEditingNote = (note) => {
  setEditingNoteId(note.id)
  setEditingNoteText(note.note)
}

const cancelEditingNote = () => {
  setEditingNoteId(null)
  setEditingNoteText('')
}

const updateDetailNote = async (noteId) => {
  const trimmedNote = editingNoteText.trim()

  if (!trimmedNote) {
    showNotification('Note cannot be empty', 'error')
    return
  }

  setNoteActionLoading(true)

  try {
    const response = await fetch(
      `/api/questions/${encodeURIComponent(
        detailQuestion.id
      )}/notes/${noteId}/`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          note: trimmedNote,
        }),
      }
    )

    let data = {}

    try {
      data = await response.json()
    } catch {
      data = {}
    }

    if (!response.ok) {
      throw new Error(
        data.error ||
          data.message ||
          `Failed to update note (${response.status})`
      )
    }

    const updatedNote = data.note

    setDetailNotes((current) =>
      current.map((note) =>
        note.id === noteId
          ? updatedNote
          : note
      )
    )

    cancelEditingNote()

    showNotification('Note updated successfully', 'success')
  } catch (error) {
    console.error('Failed to update note:', error)

    showNotification(
      error.message || 'Failed to update note',
      'error'
    )
  } finally {
    setNoteActionLoading(false)
  }
}

const deleteDetailNote = async (noteId) => {
  const confirmed = window.confirm(
    'Delete this note? This cannot be undone.'
  )

  if (!confirmed) return

  setNoteActionLoading(true)

  try {
    const response = await fetch(
      `/api/questions/${encodeURIComponent(
        detailQuestion.id
      )}/notes/${noteId}/`,
      {
        method: 'DELETE',
      }
    )

    let data = {}

    try {
      data = await response.json()
    } catch {
      data = {}
    }

    if (!response.ok) {
      throw new Error(
        data.error ||
          data.message ||
          `Failed to delete note (${response.status})`
      )
    }

    setDetailNotes((current) =>
      current.filter((note) => note.id !== noteId)
    )

    if (editingNoteId === noteId) {
      cancelEditingNote()
    }

    showNotification('Note deleted', 'success')
  } catch (error) {
    console.error('Failed to delete note:', error)

    showNotification(
      error.message || 'Failed to delete note',
      'error'
    )
  } finally {
    setNoteActionLoading(false)
  }
}

  const saveDetailNote = async () => {
  const trimmedNote = detailNoteDraft.trim()

  if (!detailQuestion) return

  if (!trimmedNote) {
    showNotification('Please enter a note first', 'error')
    return
  }

  setNoteActionLoading(true)

  try {
    const response = await fetch(
      `/api/questions/${encodeURIComponent(detailQuestion.id)}/notes/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          note: trimmedNote,
        }),
      }
    )

    let data = {}

    try {
      data = await response.json()
    } catch {
      data = {}
    }

    if (!response.ok) {
      throw new Error(
        data.error ||
          data.message ||
          `Failed to save note (${response.status})`
      )
    }

    const newNote = data.note

    setDetailNotes((current) => [
      newNote,
      ...current,
    ])

    setDetailNoteDraft('')

    showNotification('Note saved successfully', 'success')
  } catch (error) {
    console.error('Failed to save note:', error)

    showNotification(
      error.message || 'Failed to save note',
      'error'
    )
  } finally {
    setNoteActionLoading(false)
  }
}

  const renderOptionExplanations = (explanations) => {
    const labels = { a: 'A', b: 'B', c: 'C', d: 'D' }

    const entries = Object.entries(labels)
      .map(([key, label]) => [key, explanations?.[key], label])
      .filter(([, explanation]) => explanation)

    if (!entries.length) return null

    return (
      <div className="option-explanations">
        {entries.map(([key, explanation, label]) => (
          <div className="option-explanation" key={key}>
            <span>{label}</span>
            <p>{explanation}</p>
          </div>
        ))}
      </div>
    )
  }

  const renderQuestionDetail = () => {
    if (detailLoading) {
      return (
        <section className="question-detail-page">
          <div className="question-detail-loading">
            Loading question...
          </div>
        </section>
      )
    }

    if (detailError || !detailQuestion) {
      return (
        <section className="question-detail-page">
          <div className="question-detail-card">
            <button
              className="back-to-questions"
              onClick={closeQuestion}
            >
              <ChevronLeft size={16} />
              Back to questions
            </button>

            <div className="empty-state">
              <strong>
                {detailError || 'Question could not be loaded.'}
              </strong>
              <span>
                Check that the question API is available, then try again.
              </span>
            </div>
          </div>
        </section>
      )
    }

    const item = detailQuestion
    const options = item.options || {}
    const currentQuestionIndex = questions.findIndex(
      (question) => question.id === item.id
    )
    const hasPreviousQuestion =
      currentQuestionIndex > 0 || page > 1
    const hasNextQuestion =
      (currentQuestionIndex !== -1 && currentQuestionIndex < questions.length - 1) ||
      page < pagination.pages
    const result = detailFeedback
    const optionExplanations =
      result?.option_explanations || item.option_explanations || {}

    return (
      <section className="question-detail-page">
        <div className="question-detail-topbar">
          <button className="back-to-questions" onClick={closeQuestion}>
            <ChevronLeft size={16} />
            Back to questions
          </button>

          <div className="question-detail-status">
            {detailAttempted && (
              <span className="attempted-badge">✓ Attempted</span>
            )}
          </div>
        </div>

        <article className="question-detail-card">
          <div className="question-detail-navigation" aria-label="Question navigation">
            <button
              type="button"
              className="question-nav-button previous"
              onClick={() => navigateQuestion(-1)}
              disabled={!hasPreviousQuestion}
            >
              <ChevronLeft size={16} />
              <span>Previous</span>
            </button>

            <div className="question-nav-position">
              <span>Question</span>
              {currentQuestionIndex !== -1 && (
                <strong>
                  {currentQuestionIndex + 1 + (page - 1) * PAGE_SIZE}
                  <span> / {pagination.total || questions.length}</span>
                </strong>
              )}
            </div>

            <button
              type="button"
              className="question-nav-button next"
              onClick={() => navigateQuestion(1)}
              disabled={!hasNextQuestion}
            >
              <span>Next question</span>
              <ChevronRight size={16} />
            </button>
          </div>

          <div className="question-detail-meta">
            <span className={`stage-pill ${item.stage}`}>
              {item.stage === 'prelims' ? 'PRELIMS' : 'MAINS'}
            </span>
            <span>{item.paper_name || item.paper}</span>
            <span>·</span>
            <span>{item.year}</span>
            <span>·</span>
            <span>Q{item.question_number}</span>

            {item.difficulty && (
              <>
                <span>·</span>
                <span>{item.difficulty}</span>
              </>
            )}
          </div>

          <div className="question-detail-linkage">
            {item.subject || item.section || 'General Studies'}
            {item.topic ? `  ›  ${item.topic}` : ''}
          </div>

          <div className="question-detail-actions" aria-label="Question actions">
            <button
              type="button"
              className={`detail-action-button ${
                bookmarks.includes(item.id) ? 'is-active bookmark-action' : ''
              }`}
              aria-pressed={bookmarks.includes(item.id)}
              onClick={() => toggleBookmark(item.id)}
            >
              <Bookmark
                size={16}
                fill={bookmarks.includes(item.id) ? 'currentColor' : 'none'}
              />
              <span>
                {bookmarks.includes(item.id) ? 'Bookmarked' : 'Bookmark'}
              </span>
            </button>

            <button
              type="button"
              className={`detail-action-button ${
                reviewQuestions.includes(item.id) ? 'is-active review-action' : ''
              }`}
              aria-pressed={reviewQuestions.includes(item.id)}
              onClick={() => toggleReviewQuestion(item.id)}
            >
              <Flag
                size={16}
                fill={reviewQuestions.includes(item.id) ? 'currentColor' : 'none'}
              />
              <span>
                {reviewQuestions.includes(item.id)
                  ? 'Marked for review'
                  : 'Mark for review'}
              </span>
            </button>
          </div>

          <h1 className="question-detail-title">{item.question}</h1>

          {item.stage === 'mains' && (
            <div className="question-detail-stats">
              {item.marks != null && (
                <div className="detail-stat">
                  <strong>{item.marks}</strong>
                  <span>Marks</span>
                </div>
              )}

              {(item.max_word_limit != null ||
                item.word_limit != null) && (
                <div className="detail-stat">
                  <strong>
                    {item.max_word_limit ?? item.word_limit}
                  </strong>
                  <span>Words</span>
                </div>
              )}
            </div>
          )}

          {item.stage === 'prelims' &&
            Object.keys(options).length > 0 && (
              <>
                <div className="detail-options">
                  {Object.entries(options).map(([key, value]) => {
                    const selected = detailAnswer === key
                    const correct =
                      result?.correct_answer &&
                      String(result.correct_answer).toLowerCase() ===
                        key.toLowerCase()

                    return (
                      <label
                        className={[
                          'detail-option',
                          selected ? 'selected' : '',
                          correct ? 'correct' : '',
                        ].join(' ')}
                        key={key}
                      >
                        <input
                          type="radio"
                          name={`detail-${item.id}`}
                          value={key}
                          checked={selected}
                          disabled={detailSubmitting}
                          onChange={() => setDetailAnswer(key)}
                        />
                        <span className="option-letter">
                          {key.toUpperCase()}
                        </span>
                        <span className="option-text">{value}</span>

                        {selected && (
                          <span className="selected-marker">
                            Your answer
                          </span>
                        )}
                      </label>
                    )
                  })}
                </div>

                <button
                  className="detail-submit-button"
                  onClick={() => submitDetailAnswer()}
                  disabled={!detailAnswer || detailSubmitting}
                >
                  <Send size={15} />
                  {detailSubmitting ? 'Submitting...' : 'Submit answer'}
                </button>
              </>
            )}

          {item.stage === 'mains' && (
            <>
               <label className="detail-upload-box">
                 <input
                   type="file"
                   accept=".pdf,image/jpeg,image/png,image/webp,application/pdf"
                   disabled={detailSubmitting}
                   onChange={(event) => {
                     const file = event.target.files?.[0]
                     if (!file) return

                     submitDetailAnswer(file)
                     event.target.value = ''
                   }}
                 />

                 <div className="detail-upload-icon">
                   <FileText size={21} />
                 </div>

                 <div className="detail-upload-content">
                   <strong>Upload your answer sheet</strong>

                   <span className="detail-upload-description">
                     PDF, JPG, PNG or WEBP. Uploading marks this question as attempted.
                   </span>
                 </div>

                 <span className="detail-upload-action">
                   {detailSubmitting ? 'Submitting...' : 'Choose file'}
                 </span>
               </label>

              {detailAttempted && (
                <div className="attempted-message">
                  <span>✓</span>
                  <div>
                    <strong>Answer attempted</strong>
                    <span>
                      Your submission has been recorded in your
                      history.
                    </span>
                  </div>
                </div>
              )}
            </>
          )}

          {item.stage === 'prelims' && result && (
            <div
              className={`detail-result ${
                result.is_correct ? 'correct' : 'wrong'
              }`}
            >
              <div className="detail-result-header">
                <strong>
                  {result.is_correct
                    ? 'Correct answer'
                    : 'Incorrect answer'}
                </strong>

                <span>
                  Correct option:{' '}
                  {result.correct_answer
                    ? String(result.correct_answer).toUpperCase()
                    : 'Not available'}
                </span>
              </div>

              {renderOptionExplanations(optionExplanations)}

              {result.explanation && (
                <div className="overall-explanation">
                  <strong>Overall explanation</strong>
                  <p>{result.explanation}</p>
                </div>
              )}

              {!Object.keys(optionExplanations || {}).length &&
                !result.explanation && (
                  <div className="overall-explanation">
                    <strong>Explanation</strong>
                    <p>
                      No explanation is available for this question.
                    </p>
                  </div>
                )}
            </div>
          )}

          {detailNotes.length > 0 && (
  <section className="notes-history">
    <div className="notes-history-header">
      <div>
        <strong>Your notes</strong>
        <span>
          {detailNotes.length}{' '}
          {detailNotes.length === 1 ? 'note' : 'notes'}
        </span>
      </div>
    </div>

    <div className="notes-list">
      {detailNotes.map((note) => (
        <article
          className="saved-note"
          key={note.id}
        >
          {editingNoteId === note.id ? (
            <div className="note-edit-mode">
              <textarea
                value={editingNoteText}
                onChange={(event) =>
                  setEditingNoteText(event.target.value)
                }
                autoFocus
              />

              <div className="note-edit-actions">
                <button
                  type="button"
                  className="note-cancel-button"
                  onClick={cancelEditingNote}
                  disabled={noteActionLoading}
                >
                  <X size={13} />
                  Cancel
                </button>

                <button
                  type="button"
                  className="note-update-button"
                  onClick={() =>
                    updateDetailNote(note.id)
                  }
                  disabled={
                    noteActionLoading ||
                    !editingNoteText.trim()
                  }
                >
                  <Check size={13} />
                  Save changes
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="saved-note-header">
                <div className="note-title">
                  <span className="note-icon">
                    <FileText size={14} />
                  </span>

                  <div className="saved-note-heading">
                    <strong>Private note</strong>

                    <span>
                      {formatNoteDate(note.created_at)}
                    </span>
                  </div>
                </div>

                <div className="saved-note-actions">
                  <button
                    type="button"
                    aria-label="Edit note"
                    title="Edit note"
                    onClick={() =>
                      startEditingNote(note)
                    }
                    disabled={noteActionLoading}
                  >
                    <Pencil size={13} />
                  </button>

                  <button
                    type="button"
                    aria-label="Delete note"
                    title="Delete note"
                    onClick={() =>
                      deleteDetailNote(note.id)
                    }
                    disabled={noteActionLoading}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>

              <p>{note.note}</p>

              {note.updated_at &&
                note.updated_at !== note.created_at && (
                  <span className="saved-note-edited">
                    Edited {formatNoteDate(note.updated_at)}
                  </span>
                )}
            </>
          )}
        </article>
      ))}
    </div>
  </section>
)}

          {detailAttempts.length > 0 && (
            <section className="question-attempt-history">
              <div className="question-attempt-history-header">
                <div>
                  <strong>Attempt history</strong>
                  <span>{detailAttempts.length} {detailAttempts.length === 1 ? 'attempt' : 'attempts'} for this question</span>
                </div>
              </div>

              <div className="question-attempt-list">
                {detailAttempts.map((attempt, index) => (
                  <article className="question-attempt-item" key={attempt.id || `${attempt.attempt_id}-${index}`}>
                    <div className="question-attempt-top">
                      <strong>Attempt {detailAttempts.length - index}</strong>
                      <span>{formatHistoryDate(attempt.answered_at)}</span>
                    </div>

                    <div className="question-attempt-answer">
                      <span>Your answer</span>
                      <strong>{attempt.selected_answer || 'Written answer'}</strong>
                    </div>

                    {attempt.score != null && (
                      <div className="question-attempt-answer">
                        <span>Score</span>
                        <strong>{attempt.score}</strong>
                      </div>
                    )}

                    {attempt.elapsed_seconds != null && (
                      <div className="question-attempt-answer">
                        <span>Time</span>
                        <strong>{Math.round(attempt.elapsed_seconds)}s</strong>
                      </div>
                    )}

                    {attempt.attachment_url && (
                      <div className="attempt-attachment">
                        <div className="attempt-attachment-heading">
                          <FileText size={15} />
                          <strong>{attempt.attachment_name || 'Uploaded answer sheet'}</strong>
                        </div>

                        {(() => {
                          const attachmentName = String(
                            attempt.attachment_name || ''
                          )
                          const attachmentType = String(
                            attempt.attachment_type || ''
                          ).toLowerCase()
                          const isPdf =
                            attachmentType === 'pdf' ||
                            attachmentName.toLowerCase().endsWith('.pdf')

                          if (isPdf) {
                            return (
                              <div className="attempt-pdf-file">
                                <div className="attempt-pdf-file-icon">
                                  <FileText size={20} />
                                </div>
                                <div className="attempt-pdf-file-info">
                                  <strong>{attachmentName || 'Answer sheet PDF'}</strong>
                                  <span>PDF document · Preview disabled</span>
                                </div>
                                <a
                                  className="attempt-attachment-open"
                                  href={attempt.attachment_url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  Open PDF
                                </a>
                              </div>
                            )
                          }

                          return (
                            <div className="attempt-image-file">
                              <img
                                className="attempt-image-preview"
                                src={attempt.attachment_url}
                                alt={attachmentName || 'Uploaded answer sheet'}
                              />
                              <a
                                className="attempt-attachment-open"
                                href={attempt.attachment_url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Open uploaded answer sheet
                              </a>
                            </div>
                          )
                        })()}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </section>
          )}

          <div className="personal-notes">
            <div className="personal-notes-label">
              <strong>Personal notes</strong>
              <span>Only visible to you</span>
            </div>

            <div className="note-editor">
              <textarea
                placeholder={
  detailNotes.length
    ? 'Add another note...'
    : 'Write your approach, key points, or revision notes...'
}
                value={detailNoteDraft}
                onChange={(event) =>
                  setDetailNoteDraft(event.target.value)
                }
              />

              <button
                onClick={saveDetailNote}
               disabled={
  noteActionLoading ||
  !detailNoteDraft.trim()
}
              >
                <Save size={14} />
                Save
              </button>
            </div>
          </div>

          <footer className="question-detail-footer">
            <span className="footer-section">
              {item.section || 'General Studies'}
            </span>
            <span className="answer-type">
              {item.stage === 'mains' ? 'Written answer' : 'MCQ'}
            </span>
          </footer>
        </article>
      </section>
    )
  }

  useEffect(() => {
    loadProfile()
    loadGoals()
    loadReviews()
    const route = (window.location.hash || '#practice').slice(1)
    if (getQuestionKeyFromHash()) {
      setView('question')
    } else if (route === 'questions') {
      setView('practice')
    } else if (
      ['syllabus', 'practice', 'bookmarks', 'history', 'review', 'quiz', 'account'].includes(route)
    ) {
      setView(route)
    } else {
      window.location.hash = 'practice'
      setView('practice')
    }
  }, [])


  const changeStage = (value) => {
    setLoading(true)
    setStage(value)
    setPaper('all')
    setNode('')
    setPage(1)
  }

  const changeFilter = (setter) => (event) => {
    setLoading(true)
    setter(event.target.value)
    setPage(1)
  }

  const changePracticeSubject = (value) => {
    setPracticeSubject(value)
    setQuery(value === 'all' ? '' : value)
    setPage(1)
    setLoading(true)
  }

  const formatHistoryDate = (value) => {
    if (!value) return '—'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return '—'
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }).format(date)
  }

  const openHistoryQuestion = (questionKey) => {
    if (questionKey) openQuestion(questionKey)
  }

  // Question IDs are stage-prefixed by the backend (prelims- / mains-).
  // Use that as the final source of truth so a Mains question can never be
  // rendered or submitted as a Prelims question because of stale metadata.
  const quizQuestionStage = String(quizQuestion?.id || '').startsWith('mains-')
    ? 'mains'
    : 'prelims'

  return (
    <>
      {/* Floating toast – never affects page layout */}
      {notification.message && (
        <div
          className={`toast-notification ${notification.type}`}
          role="status"
          aria-live="polite"
        >
          <span className="toast-icon">
            {notification.type === 'success' ? '✓' : '×'}
          </span>
          <span>{notification.message}</span>
        </div>
      )}

      <main className="app-shell">
        <aside className="sidebar">
          <a className="brand" href="#top">
            <span className="brand-mark">i</span>
            <span>IasCode</span>
          </a>

          <nav aria-label="Primary navigation">
            {[
              ['practice', 'Practice', FileText],
              ['bookmarks', 'Bookmarks', Bookmark],
              ['history', 'History', HistoryIcon],
              ['review', `Review${(reviews.filter((r) => r.status === 'open').length) ? ` ${reviews.filter((r) => r.status === 'open').length}` : ''}`, Flag],
              ['quiz', 'Quiz', Shuffle],
              ['account', 'Account', User],
            ].map(([key, label, Icon]) => (
              <button
                key={key}
                className={`nav-item ${
                  view === key || (key === 'practice' && view === 'question')
                    ? 'active'
                    : ''
                }`}
                onClick={() => navigateTo(key)}
              >
                <Icon size={19} />
                {label}
              </button>
            ))}

            <button
              className={`nav-item ${view === 'syllabus' ? 'active' : ''}`}
              onClick={() => navigateTo('syllabus')}
            >
              <BookOpen size={19} /> Syllabus
            </button>
          </nav>

          <div className="sidebar-spacer" />

          <a className="nav-item" href="#settings">
            <Settings size={19} /> Settings
          </a>

          <div className="profile">
            <span>{(profileData?.learner?.display_name || profileData?.learner?.username || 'U').slice(0, 2).toUpperCase()}</span>
            <div>
              <strong>{profileData?.learner?.display_name || profileData?.learner?.username || 'Account'}</strong>
              <small>{profileData?.learner?.target_exam || 'Learner'}{profileData?.learner?.target_year ? ` ${profileData.learner.target_year}` : ''}</small>
            </div>
          </div>
        </aside>

        <section className="content" id="top">
          <header className="topbar">
            <div className="crumb">
              <span>IASCode</span>
              <strong>
                {view === 'question'
                  ? 'Question'
                  : view === 'practice'
                    ? 'Practice'
                    : view[0]?.toUpperCase() + view.slice(1)}
              </strong>
            </div>

            <div className="page-switcher">
              {[
                ['practice', 'Practice', FileText],
                ['bookmarks', 'Bookmarks', Bookmark],
                ['history', 'History', HistoryIcon],
                ['review', `Review${reviews.filter((r) => r.status === 'open').length ? ` ${reviews.filter((r) => r.status === 'open').length}` : ''}`, Flag],
                ['quiz', 'Quiz', Shuffle],
                ['account', 'Account', User],
              ].map(([key, label, Icon]) => (
                <button
                  key={key}
                  className={view === key || (key === 'practice' && view === 'question') ? 'selected' : ''}
                  onClick={() => navigateTo(key)}
                >
                  <Icon size={15} /> {label}
                </button>
              ))}
            </div>

            <div className="account-area">
              <span className="account-name">{profileData?.learner?.display_name || profileData?.learner?.username || 'Account'}</span>
              <span className="topbar-count">
                {pagination.total.toLocaleString()} PYQs
              </span>
            </div>
          </header>

          {view === 'question' && renderQuestionDetail()}

          {view === 'syllabus' && (
            <section
              className="questions-page syllabus-browser"
              id="syllabus"
            >
              <div className="page-head">
                <div>
                  <p className="eyebrow">
                    UPSC Civil Services Examination
                  </p>
                  <h1>The complete syllabus.</h1>
                  <p className="lede">
                    The full paper, subject, and topic structure in one
                    place. Question counts show where your practice
                    material connects.
                  </p>
                </div>

                <div className="question-mark">
                  <BookOpen size={26} />
                  <strong>9 papers</strong>
                  <span>177 official topics</span>
                </div>
              </div>

              <div className="hierarchy-list">
                {hierarchy.map((paperItem) => (
                  <details
                    className="hierarchy-paper"
                    key={paperItem.id}
                    open
                  >
                    <summary>
                      <span>
                        <strong>{paperItem.name}</strong>
                        <small>{paperItem.subtitle}</small>
                      </span>
                      <b>{paperItem.question_count} questions linked</b>
                      <ChevronDown size={18} />
                    </summary>

                    <div className="subject-list">
                      {paperItem.subjects.map((subject) => (
                        <details
                          className="hierarchy-subject"
                          key={subject.id}
                          open
                        >
                          <summary>
                            <span>
                              <strong>{subject.label}</strong>
                              <small>
                                {subject.topics.length} syllabus topics
                              </small>
                            </span>
                            <b>{subject.question_count} linked</b>
                            <ChevronDown size={16} />
                          </summary>

                          <div className="topic-list">
                            {subject.topics.map((topic) => (
                              <div
                                className="topic-row"
                                key={topic.id}
                              >
                                <span>
                                  <strong>{topic.label}</strong>
                                  <small>
                                    {topic.question_count} questions
                                    linked to this topic
                                  </small>
                                </span>
                                <b>{topic.question_count}</b>
                              </div>
                            ))}
                          </div>
                        </details>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            </section>
          )}

          {view === 'practice' && (
            <section className="questions-page practice-page" id="practice">
              <div className="page-head">
                <div>
                  <p className="eyebrow">
                    UPSC Civil Services Examination
                  </p>
                  <h1>Question library.</h1>
                  <p className="lede">
                    Work through the questions that shaped the exam.
                    Filter by stage, paper, year, or topic.
                  </p>
                </div>

                <div className="question-mark">
                  <FileText size={26} />
                  <strong>PYQs</strong>
                  <span>2012 to 2025</span>
                </div>
              </div>

              <div className="attempt-bar">
                <span>
                  <strong>Saksham Mathur</strong> · submit each answer
                  on its question
                </span>
              </div>

              <section className="question-toolbar">
                <div
                  className="stage-tabs"
                  role="group"
                  aria-label="Question stage"
                >
                  {['all', 'prelims', 'mains'].map((item) => (
                    <button
                      className={stage === item ? 'selected' : ''}
                      key={item}
                      onClick={() => changeStage(item)}
                    >
                      {item === 'all'
                        ? 'All questions'
                        : item[0].toUpperCase() + item.slice(1)}
                    </button>
                  ))}
                </div>

                <select
                  aria-label="Filter by subject"
                  value={practiceSubject}
                  onChange={(event) => changePracticeSubject(event.target.value)}
                >
                  <option value="all">All subjects</option>
                  {[
                    'History',
                    'Polity',
                    'Geography',
                    'Economy',
                    'Environment',
                    'Science',
                    'Society',
                    'Governance',
                    'International Relations',
                    'Ethics',
                    'Essay',
                    'Sociology',
                  ].map((subjectName) => (
                    <option key={subjectName} value={subjectName}>
                      {subjectName}
                    </option>
                  ))}
                </select>

                <label className="search-field">
                  <Search size={18} />
                  <input
                    value={query}
                    onChange={(event) => {
                      setLoading(true)
                      setQuery(event.target.value)
                      setPage(1)
                    }}
                    placeholder="Search questions or topics"
                  />
                </label>

                <div className="select-row">
                  <select
                    aria-label="Filter by paper"
                    value={paper}
                    onChange={changeFilter(setPaper)}
                  >
                    {paperOptions[stage].map((item) => (
                      <option key={item} value={item}>
                        {item === 'all'
                          ? 'All papers'
                          : item.toUpperCase()}
                      </option>
                    ))}
                  </select>

                  <select
                    aria-label="Filter by year"
                    value={year}
                    onChange={changeFilter(setYear)}
                  >
                    <option value="all">All years</option>
                    {Array.from(
                      { length: 14 },
                      (_, index) => 2025 - index
                    ).map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </div>
              </section>

              <div className="results-heading">
                <span>
                  {loading
                    ? 'Loading questions...'
                    : `${pagination.total.toLocaleString()} questions`}
                </span>
                <span>
                  Page {pagination.page} of{' '}
                  {Math.max(pagination.pages, 1)}
                </span>
              </div>

              {error && (
                <div className="empty-state">
                  <strong>Questions could not be loaded.</strong>
                  <span>
                    Check that the Django API is running, then refresh.
                  </span>
                </div>
              )}

              {!error && !loading && questions.length === 0 && (
                <div className="empty-state">
                  <strong>No questions match these filters.</strong>
                  <span>
                    Try a broader search or choose another paper.
                  </span>
                </div>
              )}

              <div className="question-list">
               {questions.map((item) => {
  const savedNote = notes[item.id]
  const noteDraft = noteDrafts[item.id] || ''
  const caRelevant = isCurrentAffairsRelevant(
    item.current_affairs_relevance
  )

  return (
    <article className="question-card practice-question-card" key={item.id}>

      {/* Question header */}
      <div className="question-card-header">
        <div className="question-meta">
          <span className={`stage-pill ${item.stage}`}>
            {item.stage === 'prelims' ? 'PRELIMS' : 'MAINS'}
          </span>

          <span className="question-paper">
            {item.paper_name || item.paper}
          </span>

          <span className="meta-separator">·</span>
          <span className="question-year">{item.year}</span>
          <span className="meta-separator">·</span>
          <span className="question-number">Q{item.question_number}</span>
        </div>

        <div className="question-header-right">
          {item.difficulty && (
            <span className="difficulty">
              {item.difficulty}
            </span>
          )}

          <button
            className={`bookmark-button ${
              bookmarks.includes(item.id) ? 'bookmarked' : ''
            }`}
            aria-label={
              bookmarks.includes(item.id)
                ? 'Remove bookmark'
                : 'Bookmark question'
            }
            onClick={() => toggleBookmark(item.id)}
          >
            <Bookmark
              size={17}
              fill={
                bookmarks.includes(item.id)
                  ? 'currentColor'
                  : 'none'
              }
            />
          </button>
        </div>
      </div>

      {/* Syllabus linkage */}
      <div className="question-context">
        <span className="context-item">
          {item.subject || item.section || 'General Studies'}
        </span>

        {item.topic && (
          <>
            <ChevronRight size={14} />
            <span className="context-topic">{item.topic}</span>
          </>
        )}
      </div>

      {/* Question */}
      <button
        type="button"
        className="question-body question-click-area"
        onClick={() => openQuestion(item.id)}
        aria-label={`Open question ${item.question_number}`}
      >
        <div className="question-label">QUESTION</div>
        <h2 className="question-text">{item.question}</h2>
      </button>

      {/* Mains metadata */}
      {item.stage === 'mains' && (
        <div className="mains-info">
          {item.marks != null && (
            <div className="info-chip">
              <span className="info-chip-value">{item.marks}</span>
              <span className="info-chip-label">Marks</span>
            </div>
          )}

          {item.max_word_limit != null && (
            <div className="info-chip">
              <span className="info-chip-value">{item.max_word_limit}</span>
              <span className="info-chip-label">Words</span>
            </div>
          )}

          <div className="info-chip muted">
            <span className="info-chip-value">Written</span>
            <span className="info-chip-label">Answer type</span>
          </div>
        </div>
      )}

      {/* Current affairs */}
      {caRelevant && (
        <div className="current-affairs-card">
          <div className="ca-header">
            <div className="ca-title">
              <span className="ca-dot" />
              Current Affairs
            </div>
            <span className="ca-badge">Relevant</span>
          </div>

          <div className="ca-grid">
            {item.current_affairs_window && (
              <div className="ca-field">
                <span>Window</span>
                <strong>{item.current_affairs_window}</strong>
              </div>
            )}

            {item.current_affairs_medium && (
              <div className="ca-field">
                <span>Medium</span>
                <strong>{item.current_affairs_medium}</strong>
              </div>
            )}

            {item.current_affairs_source && (
              <div className="ca-field">
                <span>Source</span>
                <strong>{item.current_affairs_source}</strong>
              </div>
            )}
          </div>

          {item.current_affairs_evidence && (
            <div className="ca-evidence">
              <span>Why it matters</span>
              <p>{item.current_affairs_evidence}</p>
            </div>
          )}

          {item.current_affairs_link && (
            <a
              href={item.current_affairs_link}
              target="_blank"
              rel="noreferrer"
              className="ca-source-link"
            >
              View source
              <ChevronRight size={14} />
            </a>
          )}
        </div>
      )}

      {/* Open question */}
      <button
        type="button"
        className="detail-submit-button question-open-button"
        onClick={() => openQuestion(item.id)}
      >
        <FileText size={15} />
        Open question &amp; submit answer
        <ChevronRight size={15} />
      </button>

      {/* Saved private note */}
      {savedNote && (
        <div className="saved-note">
          <div className="saved-note-header">
            <div className="note-title">
              <span className="note-icon">
                <FileText size={14} />
              </span>
              <strong>Private note</strong>
            </div>

            <span className="saved-note-status">Saved</span>
          </div>

          <p>{savedNote}</p>
        </div>
      )}

      {/* New note */}
      <div className="personal-notes">
        <div className="personal-notes-label">
          <strong>Personal notes</strong>
          <span>Only visible to you</span>
        </div>

        <div className="note-editor">
          <textarea
            placeholder={
              savedNote
                ? 'Add another note...'
                : 'Write your approach, key points, or revision notes...'
            }
            value={noteDraft}
            onChange={(event) =>
              setNoteDrafts((current) => ({
                ...current,
                [item.id]: event.target.value,
              }))
            }
          />

          <button
            type="button"
            onClick={() => saveNote(item.id, noteDraft)}
            disabled={!noteDraft.trim()}
          >
            <Save size={14} />
            Save
          </button>
        </div>
      </div>

      {/* Footer */}
      <footer className="question-footer">
        <span>{item.section || 'General Studies'}</span>
        <span>{item.stage === 'mains' ? 'Written answer' : 'MCQ'}</span>
      </footer>

    </article>
  )
})}
              </div>

              <div className="pagination">
                <button
                  aria-label="Previous page"
                  disabled={page <= 1}
                  onClick={() => {
                    setLoading(true)
                    setPage((current) => current - 1)
                  }}
                >
                  <ChevronLeft size={17} />
                </button>

                <span>
                  {pagination.total
                    ? `${(page - 1) * PAGE_SIZE + 1}-${Math.min(
                        page * PAGE_SIZE,
                        pagination.total
                      )} of ${pagination.total}`
                    : '0 questions'}
                </span>

                <button
                  aria-label="Next page"
                  disabled={page >= pagination.pages}
                  onClick={() => {
                    setLoading(true)
                    setPage((current) => current + 1)
                  }}
                >
                  <ChevronRight size={17} />
                </button>
              </div>
            </section>

          )}

          {view === 'bookmarks' && (
            <section className="questions-page bookmarks-page" id="bookmarks">
              <div className="page-head">
                <div>
                  <p className="eyebrow">Saved for later</p>
                  <h1>Your bookmarks.</h1>
                  <p className="lede">
                    Keep important PYQs in one place for revision.
                  </p>
                </div>
                <div className="question-mark">
                  <Bookmark size={26} />
                  <strong>{bookmarkItems.length}</strong>
                  <span>saved questions</span>
                </div>
              </div>

              {!bookmarkItems.length ? (
                <div className="empty-state">
                  <strong>No bookmarks yet.</strong>
                  <span>Bookmark a question from Practice to see it here.</span>
                </div>
              ) : (
                <div className="question-list">
                  {bookmarkItems.map((item) => (
                    <article className="question-card" key={item.id}>
                      <div className="question-card-header">
                        <div className="question-meta">
                          <span className={`stage-pill ${item.stage}`}>
                            {item.stage === 'prelims' ? 'PRELIMS' : 'MAINS'}
                          </span>
                          <span className="question-paper">{item.paper_name || item.paper}</span>
                          <span className="meta-separator">·</span>
                          <span className="question-year">{item.year}</span>
                          <span className="meta-separator">·</span>
                          <span className="question-number">Q{item.question_number}</span>
                        </div>
                        <button
                          className="bookmark-button bookmarked"
                          onClick={() => {
                            toggleBookmark(item.id)
                            setBookmarkItems((current) =>
                              current.filter((saved) => saved.id !== item.id)
                            )
                          }}
                          aria-label="Remove bookmark"
                        >
                          <Bookmark size={17} fill="currentColor" />
                        </button>
                      </div>

                      <div className="question-context">
                        <span className="context-item">
                          {item.subject || item.section || 'General Studies'}
                        </span>
                        {item.topic && (
                          <>
                            <ChevronRight size={14} />
                            <span className="context-topic">{item.topic}</span>
                          </>
                        )}
                      </div>

                      <button
                        type="button"
                        className="question-body question-click-area"
                        onClick={() => openQuestion(item.id)}
                      >
                        <div className="question-label">QUESTION</div>
                        <h2 className="question-text">{item.question}</h2>
                      </button>

                      <button
                        type="button"
                        className="detail-submit-button question-open-button"
                        onClick={() => openQuestion(item.id)}
                      >
                        <FileText size={15} />
                        Open question
                        <ChevronRight size={15} />
                      </button>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {view === 'history' && (
            <section className="questions-page history-page" id="history">
              <div className="page-head">
                <div>
                  <p className="eyebrow">Your activity</p>
                  <h1>Question history.</h1>
                  <p className="lede">
                    Every submitted question, with the time and result recorded.
                  </p>
                </div>
                <div className="question-mark">
                  <HistoryIcon size={26} />
                  <strong>{historyItems.length}</strong>
                  <span>attempts</span>
                </div>
              </div>

              {!historyItems.length ? (
                <div className="empty-state">
                  <strong>No attempts yet.</strong>
                  <span>Submit a PYQ and your attempt will appear here.</span>
                </div>
              ) : (
                <div className="question-list">
                  {historyItems.map((item) => (
                    <article className="question-card history-card" key={`${item.attempt_id}-${item.question_key}`}>
                      <div className="question-card-header">
                        <div className="question-meta">
                          <span className={`stage-pill ${item.question_stage}`}>
                            {item.question_stage === 'prelims' ? 'PRELIMS' : 'MAINS'}
                          </span>
                          <span className="question-paper">{item.paper_name || item.paper || 'PYQ'}</span>
                          <span className="meta-separator">·</span>
                          <span>{item.year || '—'}</span>
                          <span className="meta-separator">·</span>
                          <span>Q{item.question_number || '—'}</span>
                        </div>
                        <span className={`difficulty ${item.is_correct === true ? 'history-correct' : item.is_correct === false ? 'history-wrong' : ''}`}>
                          {item.is_correct === true
                            ? 'Correct'
                            : item.is_correct === false
                              ? 'Incorrect'
                              : 'Submitted'}
                        </span>
                      </div>

                      <div className="question-context">
                        <span>{item.subject || item.section || 'General Studies'}</span>
                        <span>·</span>
                        <span>{formatHistoryDate(item.answered_at)}</span>
                      </div>

                      <button
                        type="button"
                        className="question-body question-click-area"
                        onClick={() => openHistoryQuestion(item.question_key)}
                      >
                        <div className="question-label">QUESTION</div>
                        <h2 className="question-text">{item.question || item.question_key}</h2>
                      </button>

                      <div className="history-details">
                        <span>Answer: <strong>{item.selected_answer || 'Written answer'}</strong></span>
                        {item.score != null && <span>Score: <strong>{item.score}</strong></span>}
                        {item.elapsed_seconds != null && (
                          <span>Time: <strong>{Math.round(item.elapsed_seconds)}s</strong></span>
                        )}
                        {item.attempt_count > 1 && (
                          <span>Attempts: <strong>{item.attempt_count}</strong></span>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {view === 'quiz' && (
            <section className="questions-page" id="quiz">
              <div className="page-head">
                <div>
                  <p className="eyebrow">Quick practice</p>
                  <h1>Quick quiz.</h1>
                  <p className="lede">
                    Solve Prelims and Mains PYQs one at a time. Submit directly here, or skip to the next question.
                  </p>
                </div>
                <div className="question-mark">
                  <Shuffle size={26} />
                  <strong>1</strong>
                  <span>random question</span>
                </div>
              </div>

              <div className="quiz-stage-switcher" role="group" aria-label="Quiz question type">
                {['all', 'prelims', 'mains'].map((stage) => (
                  <button
                    key={stage}
                    type="button"
                    className={`quiz-stage-button ${quizStageFilter === stage ? 'active' : ''}`}
                    onClick={() => {
                      setQuizStageFilter(stage)
                      loadRandomQuizQuestion(stage)
                    }}
                    disabled={quizLoading || quizSubmitting}
                  >
                    {stage === 'all' ? 'All' : stage === 'prelims' ? 'Prelims' : 'Mains'}
                  </button>
                ))}
              </div>

              {quizLoading ? (
                <div className="empty-state"><strong>Picking a question...</strong></div>
              ) : quizQuestion ? (
                <article className="question-card quiz-card">
                  <div className="question-card-header">
                    <div className="question-meta">
                      <span className={`stage-pill ${quizQuestionStage}`}>
                        {quizQuestionStage === 'mains' ? 'MAINS' : 'PRELIMS'}
                      </span>
                      <span>{quizQuestion.paper_name || quizQuestion.paper}</span>
                      <span className="meta-separator">·</span>
                      <span>{quizQuestion.year}</span>
                      <span className="meta-separator">·</span>
                      <span>Q{quizQuestion.question_number}</span>
                    </div>
                    <button
                      type="button"
                      className={`bookmark-button ${bookmarks.includes(quizQuestion.id) ? 'bookmarked' : ''}`}
                      onClick={() => toggleBookmark(quizQuestion.id)}
                      aria-label="Bookmark question"
                    >
                      <Bookmark size={17} fill={bookmarks.includes(quizQuestion.id) ? 'currentColor' : 'none'} />
                    </button>
                  </div>

                  <div className="question-context">
                    <span>{quizQuestion.subject || quizQuestion.section || 'General Studies'}</span>
                    {quizQuestion.topic && (
                      <>
                        <ChevronRight size={14} />
                        <span>{quizQuestion.topic}</span>
                      </>
                    )}
                  </div>

                  <button
                    type="button"
                    className="question-body quiz-question-link"
                    onClick={() => openQuestion(quizQuestion.id)}
                    aria-label={`Open question ${quizQuestion.question_number || ''}`}
                  >
                    <div className="question-label">QUESTION</div>
                    <h2 className="question-text">{quizQuestion.question}</h2>
                  </button>

                  {quizQuestionStage === 'prelims' && quizQuestion.options && (
                    <div className="detail-options">
                      {Object.entries(quizQuestion.options).map(([key, value]) => {
                        const quizResult = feedback[quizQuestion.id]
                        const submitted = Boolean(quizResult)
                        const selected = responses[quizQuestion.id] === key
                        const correctKey = quizResult?.correct_answer
                          ? String(quizResult.correct_answer).toLowerCase()
                          : ''

                        return (
                          <label
                            className={`detail-option ${selected ? 'selected' : ''} ${
                              submitted && correctKey === key ? 'correct' : ''
                            } ${
                              submitted && selected && correctKey !== key ? 'wrong' : ''
                            }`}
                            key={key}
                          >
                            <input
                              type="radio"
                              name={`quiz-${quizQuestion.id}`}
                              value={key}
                              checked={selected}
                              disabled={submitted || quizSubmitting}
                              onChange={() =>
                                setResponses((current) => ({
                                  ...current,
                                  [quizQuestion.id]: key,
                                }))
                              }
                            />
                            <span className="option-letter">{key.toUpperCase()}</span>
                            <span className="option-text">{value}</span>
                            {submitted && correctKey === key && (
                              <span className="selected-marker">Correct</span>
                            )}
                            {submitted && selected && correctKey !== key && (
                              <span className="selected-marker">Your answer</span>
                            )}
                          </label>
                        )
                      })}
                    </div>
                  )}

                  {quizQuestionStage === 'mains' && !feedback[quizQuestion.id] && (
                    <label className="detail-upload-box">
                      <input
                        type="file"
                        accept=".pdf,image/jpeg,image/png,image/webp,application/pdf"
                        disabled={quizSubmitting}
                        onChange={(event) => {
                          const file = event.target.files?.[0] || null
                          setQuizAttachment(file)
                          if (file) {
                            showNotification(`${file.name} selected`, 'success')
                          }
                          event.target.value = ''
                        }}
                      />
                      <div className="detail-upload-icon">
                        <FileText size={21} />
                      </div>
                      <div className="detail-upload-content">
                        <strong>Upload your answer sheet</strong>
                        <span className="detail-upload-description">
                          PDF, JPG, PNG or WEBP. Your submission will be recorded in history.
                        </span>
                      </div>
                      <span className="detail-upload-action">
                        {quizAttachment ? quizAttachment.name : 'Choose file'}
                      </span>
                    </label>
                  )}

                  {feedback[quizQuestion.id] ? (
                    <>
                      <div
                        className={`detail-result ${
                          quizQuestionStage === 'mains'
                            ? 'correct'
                            : feedback[quizQuestion.id].is_correct
                              ? 'correct'
                              : 'wrong'
                        }`}
                      >
                        <div className="detail-result-header">
                          <strong>
                            {quizQuestionStage === 'prelims'
                              ? feedback[quizQuestion.id].is_correct
                                ? 'Correct answer'
                                : 'Incorrect answer'
                              : 'Answer submitted'}
                          </strong>
                          {quizQuestionStage === 'prelims' && (
                            <span>
                              Correct option:{' '}
                              {feedback[quizQuestion.id].correct_answer
                                ? String(feedback[quizQuestion.id].correct_answer).toUpperCase()
                                : 'Not available'}
                            </span>
                          )}
                        </div>

                        {quizQuestionStage === 'prelims' && feedback[quizQuestion.id].option_explanations &&
                          Object.entries(feedback[quizQuestion.id].option_explanations).map(([key, explanation]) => (
                            explanation ? (
                              <div className="overall-explanation" key={key}>
                                <strong>{key.toUpperCase()} explanation</strong>
                                <p>{explanation}</p>
                              </div>
                            ) : null
                          ))}

                        {quizQuestionStage === 'prelims' && feedback[quizQuestion.id].explanation && (
                          <div className="overall-explanation">
                            <strong>Explanation</strong>
                            <p>{feedback[quizQuestion.id].explanation}</p>
                          </div>
                        )}
                      </div>

                      <div className="attempted-message quiz-next-prompt">
                        <div>
                          <strong>Answer submitted.</strong>
                          <span>Do you want to solve the next question?</span>
                        </div>
                        <div className="quiz-actions">
                          <button
                            type="button"
                            className="detail-submit-button"
                            onClick={loadRandomQuizQuestion}
                          >
                            <Shuffle size={15} />
                            Next question
                          </button>
                          <button
                            type="button"
                            className="detail-submit-button secondary"
                            onClick={() => document.getElementById('quiz')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                          >
                            Stay here
                          </button>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="quiz-actions">
                      <button
                        type="button"
                        className="detail-submit-button"
                        onClick={submitQuizAnswer}
                        disabled={(quizQuestionStage === 'prelims' ? !responses[quizQuestion.id] : !quizAttachment) || quizSubmitting || quizLoading}
                      >
                        <Send size={15} />
                        {quizSubmitting ? 'Submitting...' : quizQuestionStage === 'mains' ? 'Submit answer sheet' : 'Submit answer'}
                      </button>

                      <button
                        type="button"
                        className="detail-submit-button secondary"
                        onClick={loadRandomQuizQuestion}
                        disabled={quizSubmitting || quizLoading}
                      >
                        <Shuffle size={15} />
                        Next question
                      </button>
                    </div>
                  )}
                </article>
              ) : (
                <div className="empty-state">
                  <strong>Could not load a random question.</strong>
                  <button type="button" className="detail-submit-button" onClick={loadRandomQuizQuestion}>
                    Try again
                  </button>
                </div>
              )}
            </section>
          )}

          {view === 'review' && (
            <section className="questions-page review-page" id="review">
              <div className="page-head">
                <div><p className="eyebrow">Dataset cleanup</p><h1>Review questions.</h1><p className="lede">Questions you flagged for manual cleanup and verification.</p></div>
                <div className="question-mark"><Flag size={26} /><strong>{reviews.filter((r) => r.status === 'open').length}</strong><span>open reviews</span></div>
              </div>
              <div className="review-filters">
                {['all', 'open', 'resolved', 'incorrect_option', 'incorrect_question', 'wrong_topic_tag', 'incorrect_answer_explanation', 'other'].map((filter) => (
                  <button key={filter} className={reviewFilter === filter ? 'selected' : ''} onClick={() => { setReviewFilter(filter); loadReviews(filter) }}>
                    {filter === 'all' ? 'All' : filter === 'incorrect_option' ? 'Incorrect option' : filter === 'incorrect_question' ? 'Incorrect question' : filter === 'wrong_topic_tag' ? 'Wrong tag' : filter === 'incorrect_answer_explanation' ? 'Explanation' : filter === 'other' ? 'Other' : filter[0].toUpperCase() + filter.slice(1)}
                  </button>
                ))}
              </div>
              {reviewLoading ? <div className="empty-state"><strong>Loading reviews...</strong></div> : !reviews.length ? <div className="empty-state"><strong>No reviews found.</strong><span>Mark a question for review when you find a dataset issue.</span></div> : (
                <div className="review-layout">
                  <div className="review-list">
                    {reviews.filter((r) => reviewFilter === 'all' || reviewFilter === 'open' || reviewFilter === 'resolved' || (r.reasons || []).includes(reviewFilter)).map((review) => (
                      <article className={`review-card ${selectedReview?.id === review.id ? 'selected' : ''}`} key={review.id} onClick={() => openReviewEditor(review)}>
                        <div className="review-card-top"><div className="question-meta"><span className={`stage-pill ${review.stage}`}>{review.stage?.toUpperCase()}</span><span>{review.year}</span><span>·</span><span>Q{review.question_number}</span></div><span className={`review-status ${review.status}`}>{review.status}</span></div>
                        <h2>{review.question || review.question_key}</h2>
                        <div className="review-meta"><span>{review.paper_name || review.paper || 'PYQ'}</span><span>{review.subject || review.section || 'General Studies'}</span>{review.topic && <span>{review.topic}</span>}</div>
                        <div className="review-reasons">{(review.reasons || []).map((reason) => <span key={reason}>{reason.replaceAll('_', ' ')}</span>)}</div>
                        {review.note && <p className="review-note-preview">{review.note}</p>}
                        <div className="review-card-actions"><button onClick={(e) => { e.stopPropagation(); openQuestion(review.question_key) }}>Open question</button>{review.status === 'open' && <button onClick={(e) => { e.stopPropagation(); resolveReview(review.id) }}>Resolve</button>}</div>
                      </article>
                    ))}
                  </div>
                  {selectedReview && (
                    <aside className="review-editor">
                      <div className="review-editor-header"><div><p className="eyebrow">Review information</p><h2>Cleanup details</h2></div><button onClick={() => setSelectedReview(null)}><X size={16} /></button></div>
                      <div className="review-question-summary"><strong>{selectedReview.year} · {selectedReview.stage?.toUpperCase()} · Q{selectedReview.question_number}</strong><p>{selectedReview.question}</p></div>
                      <label>Reason(s)</label>
                      <div className="reason-grid">{[['incorrect_option','Incorrect option'],['incorrect_question','Incorrect question'],['incorrect_answer_explanation','Incorrect answer/explanation'],['wrong_subject','Wrong subject'],['wrong_topic_tag','Wrong topic/tag'],['wrong_year','Wrong year'],['duplicate_question','Duplicate question'],['formatting_issue','Formatting issue'],['missing_information','Missing information'],['other','Other']].map(([key,label]) => <label key={key} className="reason-check"><input type="checkbox" checked={reviewReasons.includes(key)} onChange={() => setReviewReasons((current) => current.includes(key) ? current.filter((r) => r !== key) : [...current, key])} />{label}</label>)}</div>
                      <label>Reviewer note</label><textarea value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} placeholder="Describe the issue..." />
                      <div className="review-editor-actions"><button className="detail-submit-button" onClick={updateSelectedReview}>Save review</button>{selectedReview.status === 'open' && <button className="detail-submit-button" onClick={() => resolveReview(selectedReview.id)}>Resolve issue</button>}</div>
                    </aside>
                  )}
                </div>
              )}
            </section>
          )}

          {view === 'account' && (
            <section className="questions-page account-page" id="account">
              <div className="page-head"><div><p className="eyebrow">Learner account</p><h1>{profileData?.learner?.display_name || 'Your account'}.</h1><p className="lede">Your targets, activity, streaks and subject-level progress.</p></div><div className="question-mark"><User size={26}/><strong>{profileData?.streak?.current || 0}</strong><span>day streak</span></div></div>
              <div className="account-grid"><div className="account-stat-card"><span>Questions attempted</span><strong>{profileData?.stats?.questions_attempted || 0}</strong></div><div className="account-stat-card"><span>Bookmarks</span><strong>{profileData?.stats?.bookmarks || 0}</strong></div><div className="account-stat-card"><span>Current streak</span><strong>{profileData?.streak?.current || 0}</strong></div><div className="account-stat-card"><span>Longest streak</span><strong>{profileData?.streak?.longest || 0}</strong></div><div className="account-stat-card"><span>Review</span><strong>{profileData?.stats?.review || 0}</strong></div></div>

              <div className="account-section"><div className="account-section-header"><div><p className="eyebrow">Profile</p><h2>User details</h2></div>{!profileEditing ? <button className="account-edit-button" onClick={startProfileEdit}><Pencil size={15}/> Edit profile</button> : <div className="profile-edit-actions"><button onClick={() => setProfileEditing(false)}>Cancel</button><button className="detail-submit-button" onClick={saveProfile}>Save changes</button></div>}</div>
                {!profileEditing ? <div className="account-details"><div><span>Name</span><strong>{profileData?.learner?.display_name || '—'}</strong></div><div><span>Username</span><strong>{profileData?.learner?.username || '—'}</strong></div><div><span>Email</span><strong>{profileData?.learner?.email || '—'}</strong></div><div><span>Age</span><strong>{profileData?.learner?.age || '—'}</strong></div><div><span>Target exam</span><strong>{profileData?.learner?.target_exam || '—'}</strong></div><div><span>Target year</span><strong>{profileData?.learner?.target_year || '—'}</strong></div><div><span>Optional subject</span><strong>{profileData?.learner?.optional_subject || '—'}</strong></div><div><span>Daily study target</span><strong>{profileData?.learner?.daily_study_target_minutes ? `${Math.round(profileData.learner.daily_study_target_minutes / 60 * 10) / 10} hours` : '—'}</strong></div></div> : <div className="profile-form"><label>Name<input value={profileDraft.display_name || ''} onChange={(e)=>setProfileDraft({...profileDraft,display_name:e.target.value})}/></label><label>Email<input type="email" value={profileDraft.email || ''} onChange={(e)=>setProfileDraft({...profileDraft,email:e.target.value})}/></label><label>Age<input type="number" value={profileDraft.age || ''} onChange={(e)=>setProfileDraft({...profileDraft,age:e.target.value ? Number(e.target.value) : null})}/></label><label>Target exam<input value={profileDraft.target_exam || ''} onChange={(e)=>setProfileDraft({...profileDraft,target_exam:e.target.value})}/></label><label>Target year<input type="number" value={profileDraft.target_year || ''} onChange={(e)=>setProfileDraft({...profileDraft,target_year:e.target.value ? Number(e.target.value) : null})}/></label><label>Optional subject<input value={profileDraft.optional_subject || ''} onChange={(e)=>setProfileDraft({...profileDraft,optional_subject:e.target.value})}/></label><label>Daily study target (minutes)<input type="number" value={profileDraft.daily_study_target_minutes || ''} onChange={(e)=>setProfileDraft({...profileDraft,daily_study_target_minutes:e.target.value ? Number(e.target.value) : null})}/></label><label>Username<input value={profileDraft.username || ''} disabled/></label></div>}
              </div>

              <div className="account-section"><div className="account-section-header"><div><p className="eyebrow">Targets</p><h2>Study goals</h2></div><button className="account-edit-button" onClick={()=>setGoalEditing({name:'',exam:'',target_year:'',exam_date:'',description:'',is_active:true})}>+ Add goal</button></div>
                {goalEditing && <div className="goal-form"><input placeholder="Goal name" value={goalEditing.name} onChange={e=>setGoalEditing({...goalEditing,name:e.target.value})}/><input placeholder="Exam" value={goalEditing.exam} onChange={e=>setGoalEditing({...goalEditing,exam:e.target.value})}/><input type="number" placeholder="Target year" value={goalEditing.target_year || ''} onChange={e=>setGoalEditing({...goalEditing,target_year:e.target.value})}/><input type="date" value={goalEditing.exam_date || ''} onChange={e=>setGoalEditing({...goalEditing,exam_date:e.target.value})}/><textarea placeholder="Description" value={goalEditing.description || ''} onChange={e=>setGoalEditing({...goalEditing,description:e.target.value})}/><label><input type="checkbox" checked={goalEditing.is_active} onChange={e=>setGoalEditing({...goalEditing,is_active:e.target.checked})}/> Active goal</label><div><button onClick={()=>setGoalEditing(null)}>Cancel</button><button className="detail-submit-button" onClick={()=>saveGoal(goalEditing)}>Save goal</button></div></div>}
                <div className="goal-list">{goals.map(goal=><article className="goal-card" key={goal.id}><div className="goal-card-header"><div><strong>{goal.name}</strong><span>{goal.exam} {goal.target_year ? `· ${goal.target_year}` : ''}</span></div><ExamCountdown examDate={goal.exam_date}/></div><div className="goal-date">Exam date: {goal.exam_date || 'Not set'}</div>{goal.description && <p>{goal.description}</p>}<div className="goal-actions"><button onClick={()=>setGoalEditing({...goal})}>Edit</button><button onClick={()=>deleteGoal(goal.id)}><Trash2 size={14}/> Delete</button></div></article>)}{!goals.length && !goalEditing && <div className="empty-state"><strong>No study goals yet.</strong><span>Add your first exam target.</span></div>}</div>
              </div>

              <div className="account-section"><div className="account-section-header"><div><p className="eyebrow">Progress</p><h2>UPSC progress</h2></div></div>
                <div className="progress-section-title">PRELIMS</div><div className="progress-grid"><div className="progress-overview-card"><strong>{profileData?.progress?.prelims?.overall?.coverage || 0}%</strong><span>Overall coverage</span><small>{profileData?.progress?.prelims?.overall?.attempted || 0} / {profileData?.progress?.prelims?.overall?.total || 0} unique questions</small><b>Accuracy: {profileData?.progress?.prelims?.overall?.accuracy ?? '—'}%</b></div>{(profileData?.progress?.prelims?.subjects || []).map(record=><div className="progress-row-card" key={record.id}><div><strong>{record.label}</strong><span>{record.attempted} / {record.total} attempted · {record.coverage}% coverage</span></div><div className="progress-bar"><span style={{width:`${Math.min(record.coverage || 0,100)}%`}}/></div><small>Accuracy: {record.accuracy == null ? '—' : `${record.accuracy}%`}</small></div>)}</div>
                <div className="progress-section-title">MAINS</div><div className="progress-grid"><div className="progress-overview-card"><strong>{profileData?.progress?.mains?.overall?.coverage || 0}%</strong><span>Overall coverage</span><small>{profileData?.progress?.mains?.overall?.attempted || 0} / {profileData?.progress?.mains?.overall?.total || 0} unique questions</small></div>{(profileData?.progress?.mains?.papers || []).map(record=><div className="progress-row-card" key={record.id}><div><strong>{record.label}</strong><span>{record.attempted} / {record.total} attempted · {record.coverage}% coverage</span></div><div className="progress-bar"><span style={{width:`${Math.min(record.coverage || 0,100)}%`}}/></div>{record.average_marks != null && <small>Average marks: {record.average_marks} · Avg words: {record.average_word_count ?? '—'}</small>}</div>)}</div>
              </div>
            </section>
          )}

        </section>
      </main>
    </>
  )
}

export default App
