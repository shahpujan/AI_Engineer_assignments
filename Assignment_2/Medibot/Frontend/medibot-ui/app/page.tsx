"use client";

import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

const API_URL = "http://127.0.0.1:8000";

/* =========================================================
   TYPES
========================================================= */

type Source = {
  source_document: string;
  section_title: string;
  collection: string;
};

type ChatMessage = {
  id: string;
  type: "user" | "bot";
  text: string;
  sources?: Source[];
  isError?: boolean;
  timestamp?: string;
};

/*
  NEW:
  This is the simplified message format we send to FastAPI
  as conversation history.
*/
type HistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

type UserProfile = {
  name: string;
  icon: string;
  title: string;
};

type LoginResponse = {
  token: string;
  role: string;
};

type CollectionsResponse = {
  role: string;
  collections: string[];
};

type ChatResponse = {
  answer: string;
  sources: Source[];
  retrieval_type: string;
  role: string;
};

/* =========================================================
   USER PROFILES
========================================================= */

const USER_PROFILES: Record<string, UserProfile> = {
  "dr.mehta": {
    name: "Dr. Pankaj Mehta",
    icon: "🩺",
    title: "Doctor",
  },

  "nurse.priya": {
    name: "Priya Patel",
    icon: "💉",
    title: "Nurse",
  },

  "billing.ravi": {
    name: "Ravi Shah",
    icon: "💳",
    title: "Billing Executive",
  },

  "tech.anand": {
    name: "Anand Rao",
    icon: "🛠️",
    title: "Technician",
  },

  "admin.sys": {
    name: "Aisha Verma",
    icon: "🛡️",
    title: "Administrator",
  },
};

/* =========================================================
   ROLE SUBTITLES
========================================================= */

const ROLE_SUBTITLES: Record<string, string> = {
  doctor:
    "Ask MediBot about clinical information, nursing procedures and general policies.",

  nurse:
    "Ask MediBot about nursing procedures, patient care and general policies.",

  billing_executive:
    "Ask MediBot about billing, claims and general policies.",

  technician:
    "Ask MediBot about equipment, maintenance and general policies.",

  admin:
    "Ask MediBot about clinical, nursing, billing, equipment and general information.",
};


/* =========================================================
   ROLE-SPECIFIC SUGGESTIONS
========================================================= */

const ROLE_SUGGESTIONS: Record<string, string[]> = {
  doctor: [
    "What clinical information is available for patient treatment?",
    "What are the nursing procedures for IV cannula care?",
    "What general hospital policies should I know?",
  ],

  nurse: [
    "What cannula size is recommended for a paediatric patient under 5 kg?",
    "What is the site selection order for IV cannula insertion?",
    "What should a nurse do after two failed IV cannula attempts?",
  ],

  billing_executive: [
    "How many total claims are present?",
    "How many claims are there by status?",
    "Which department has the highest number of claims?",
  ],

  technician: [
    "What equipment maintenance procedures are available?",
    "What information is available about equipment servicing?",
    "What general procedures apply to technicians?",
  ],

  admin: [
    "How many total claims are present?",
    "What is the site selection order for IV cannula insertion?",
    "What equipment maintenance information is available?",
  ],
};

/* =========================================================
   COLLECTION DISPLAY DETAILS
========================================================= */

const COLLECTION_DETAILS: Record<
  string,
  { icon: string; label: string }
> = {
  general: {
    icon: "📚",
    label: "General",
  },

  clinical: {
    icon: "🩺",
    label: "Clinical",
  },

  nursing: {
    icon: "💉",
    label: "Nursing",
  },

  billing: {
    icon: "💳",
    label: "Billing",
  },

  equipment: {
    icon: "🛠️",
    label: "Equipment",
  },
};

/* =========================================================
   HELPERS
========================================================= */

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function getCurrentTime() {
  return new Intl.DateTimeFormat("en-AU", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}

function formatRole(role: string) {
  return role
    .split("_")
    .map(
      (word) =>
        word.charAt(0).toUpperCase() + word.slice(1)
    )
    .join(" ");
}

/* =========================================================
   MAIN MEDI-BOT LOGO
========================================================= */

function MediBotLogo({
  compact = false,
}: {
  compact?: boolean;
}) {
  const size = compact ? 72 : 112;

  return (
    <div
      className={
        compact
          ? "flex items-center gap-3"
          : "flex flex-col items-center text-center"
      }
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="MediBot logo"
      >
        {/* Medical cross */}

        <path
          d="M45 8H75C80 8 84 12 84 17V38H105C110 38 114 42 114 47V75C114 80 110 84 105 84H84V105C84 110 80 114 75 114H45C40 114 36 110 36 105V84H15C10 84 6 80 6 75V47C6 42 10 38 15 38H36V17C36 12 40 8 45 8Z"
          fill="#0EA5E9"
          stroke="#075985"
          strokeWidth="4"
          strokeLinejoin="round"
        />

        <path
          d="M50 15H70C74 15 77 18 77 22V45H100C104 45 107 48 107 52V68C107 72 104 75 100 75H77V98C77 102 74 105 70 105H50C46 105 43 102 43 98V75H20C16 75 13 72 13 68V52C13 48 16 45 20 45H43V22C43 18 46 15 50 15Z"
          fill="#38BDF8"
          opacity="0.65"
        />

        {/* Robotic arm */}

        <path
          d="M34 83L50 65"
          stroke="#F8FAFC"
          strokeWidth="10"
          strokeLinecap="round"
        />

        <path
          d="M34 83L50 65"
          stroke="#1E3A8A"
          strokeWidth="3"
          strokeLinecap="round"
        />

        <path
          d="M50 65L72 78"
          stroke="#F8FAFC"
          strokeWidth="10"
          strokeLinecap="round"
        />

        <path
          d="M50 65L72 78"
          stroke="#1E3A8A"
          strokeWidth="3"
          strokeLinecap="round"
        />

        <path
          d="M72 78L88 56"
          stroke="#F8FAFC"
          strokeWidth="10"
          strokeLinecap="round"
        />

        <path
          d="M72 78L88 56"
          stroke="#1E3A8A"
          strokeWidth="3"
          strokeLinecap="round"
        />

        {/* Joints */}

        <circle
          cx="34"
          cy="83"
          r="8"
          fill="white"
          stroke="#1E3A8A"
          strokeWidth="4"
        />

        <circle
          cx="50"
          cy="65"
          r="8"
          fill="white"
          stroke="#1E3A8A"
          strokeWidth="4"
        />

        <circle
          cx="72"
          cy="78"
          r="8"
          fill="white"
          stroke="#1E3A8A"
          strokeWidth="4"
        />

        <circle cx="34" cy="83" r="3" fill="#0EA5E9" />
        <circle cx="50" cy="65" r="3" fill="#0EA5E9" />
        <circle cx="72" cy="78" r="3" fill="#0EA5E9" />

        {/* Robot hand */}

        <path
          d="M86 56L92 49L98 54L92 61Z"
          fill="white"
          stroke="#1E3A8A"
          strokeWidth="3"
          strokeLinejoin="round"
        />

        {/* Bandage */}

        <g transform="rotate(35 101 40)">
          <rect
            x="89"
            y="34"
            width="25"
            height="12"
            rx="6"
            fill="#FDBA74"
            stroke="#EA580C"
            strokeWidth="2.5"
          />

          <circle cx="96" cy="40" r="1.5" fill="#F97316" />
          <circle cx="101" cy="40" r="1.5" fill="#F97316" />
          <circle cx="106" cy="40" r="1.5" fill="#F97316" />
        </g>

        <path
          d="M104 23L108 16"
          stroke="#F97316"
          strokeWidth="3"
          strokeLinecap="round"
        />

        <path
          d="M112 29L118 25"
          stroke="#F97316"
          strokeWidth="3"
          strokeLinecap="round"
        />

        {/* First aid box */}

        <rect
          x="15"
          y="78"
          width="30"
          height="25"
          rx="5"
          fill="white"
          stroke="#1E3A8A"
          strokeWidth="3"
        />

        <rect
          x="27"
          y="84"
          width="6"
          height="14"
          rx="1"
          fill="#0EA5E9"
        />

        <rect
          x="23"
          y="88"
          width="14"
          height="6"
          rx="1"
          fill="#0EA5E9"
        />
      </svg>

      <div className={compact ? "" : "mt-1"}>
        <div
          className={`font-black tracking-tight text-blue-950 ${
            compact ? "text-2xl" : "text-3xl"
          }`}
        >
          MEDI-BOT
        </div>

        {!compact && (
          <p className="mt-2 text-sm text-slate-500">
            AI Assistant for MediAssist Health Network
          </p>
        )}
      </div>
    </div>
  );
}

/* =========================================================
   BOT AVATAR
========================================================= */

function BotAvatar() {
  return (
    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-blue-200 bg-blue-50 shadow-sm">
      <svg
        width="27"
        height="27"
        viewBox="0 0 24 24"
        fill="none"
      >
        <rect
          x="4"
          y="7"
          width="16"
          height="12"
          rx="4"
          fill="#E0F2FE"
          stroke="#2563EB"
          strokeWidth="1.8"
        />

        <circle cx="9" cy="13" r="1.4" fill="#2563EB" />
        <circle cx="15" cy="13" r="1.4" fill="#2563EB" />

        <path
          d="M9 16H15"
          stroke="#2563EB"
          strokeWidth="1.7"
          strokeLinecap="round"
        />

        <path
          d="M12 7V4"
          stroke="#2563EB"
          strokeWidth="1.8"
          strokeLinecap="round"
        />

        <circle cx="12" cy="3.5" r="1" fill="#2563EB" />
      </svg>
    </div>
  );
}

/* =========================================================
   USER AVATAR
========================================================= */

function UserAvatar() {
  return (
    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-blue-100 bg-blue-50 shadow-sm">
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle
          cx="12"
          cy="8"
          r="4"
          fill="#3B82F6"
        />

        <path
          d="M5 20C5 16.7 8.1 14 12 14C15.9 14 19 16.7 19 20"
          fill="#3B82F6"
        />
      </svg>
    </div>
  );
}

/* =========================================================
   MAIN COMPONENT
========================================================= */

export default function Home() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [token, setToken] = useState("");
  const [role, setRole] = useState("");

  const [collections, setCollections] = useState<string[]>([]);

  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const [question, setQuestion] = useState("");

  const [loading, setLoading] = useState(false);
  const [loginLoading, setLoginLoading] = useState(false);

  const [loginError, setLoginError] = useState("");

  const [apiConnected, setApiConnected] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const profile =
    USER_PROFILES[username] ?? {
      name: username,
      icon: "👤",
      title: formatRole(role),
    };  

  /* =========================================================
     AUTO SCROLL
  ========================================================= */

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  /* =========================================================
     COLLECTIONS
  ========================================================= */

  async function loadCollections(
    authToken: string,
    currentRole: string,
    currentUsername: string
  ) {
    try {
      const response = await fetch(
        `${API_URL}/collections/${currentRole}`,
        {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error("Unable to load collections.");
      }

      const data: CollectionsResponse = await response.json();

      setCollections(data.collections);

      const currentProfile =
        USER_PROFILES[currentUsername] ?? {
          name: currentUsername,
          icon: "👤",
          title: formatRole(currentRole),
        };

      setMessages([
        {
          id: createMessageId(),

          type: "bot",

          timestamp: getCurrentTime(),

          text:
            `Hello, ${currentProfile.name}! 👋\n\n` +
            `I'm MediBot, your AI assistant at MediAssist Health Network.\n\n` +
            `You're logged in as ${formatRole(
              currentRole
            )} with access to ${data.collections
              .map((collection) => formatRole(collection))
              .join(", ")}.\n\n` +
            `How can I help you today?`,
        },
      ]);
    } catch (error) {
      console.error(error);
    }
  }

  /* =========================================================
     LOGIN
  ========================================================= */

  async function handleLogin(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setLoginLoading(true);
    setLoginError("");

    try {
      const response = await fetch(`${API_URL}/login`, {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          username,
          password,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);

        throw new Error(
          errorData?.detail ?? "Invalid username or password."
        );
      }

      const data: LoginResponse = await response.json();

      setToken(data.token);
      setRole(data.role);
      setApiConnected(true);

      await loadCollections(
        data.token,
        data.role,
        username
      );
    } catch (error) {
      setApiConnected(false);

      if (error instanceof Error) {
        setLoginError(error.message);
      } else {
        setLoginError("Unable to log in.");
      }
    } finally {
      setLoginLoading(false);
    }
  }

  /* =========================================================
     LOGOUT
  ========================================================= */

  function handleLogout() { 

    setToken("");
    setRole("");
    setUsername("");
    setPassword("");
    setCollections([]);
    setMessages([]);
    setQuestion("");
    setLoginError("");
    setApiConnected(false);
  }

  /* =========================================================
     SEND CHAT
     
     IMPORTANT:
     This now sends recent conversation history.
  ========================================================= */

  async function sendQuestion(questionText?: string) {
    const finalQuestion = (
      questionText ?? question
    ).trim();

    if (!finalQuestion || loading) {
      return;
    }

    /*
      ---------------------------------------------------------
      NEW — BUILD CONVERSATION HISTORY

      We:
      1. Ignore the initial MediBot welcome message
      2. Ignore RBAC/error messages
      3. Keep only recent conversation turns
      4. Convert UI format into API format
      ---------------------------------------------------------
    */

    const chatHistory: HistoryMessage[] = messages
      .slice(1)
      .filter((message) => !message.isError)
      .slice(-6)
      .map((message) => ({
        role:
          message.type === "user"
            ? "user"
            : "assistant",

        content: message.text,
      }));

    /*
      Current question is NOT added to chatHistory here.

      It will be sent separately as "question".

      Example:

      chat_history:
        User: Tell me about IV cannula
        Assistant: ...

      question:
        What about children under 5 kg?
    */

    const userMessage: ChatMessage = {
      id: createMessageId(),

      type: "user",

      text: finalQuestion,

      timestamp: getCurrentTime(),
    };

    setMessages((previous) => [
      ...previous,
      userMessage,
    ]);

    setQuestion("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },

        /*
          NEW:
          chat_history is now sent to FastAPI.
        */

        body: JSON.stringify({
          question: finalQuestion,
          role,
          chat_history: chatHistory,
        }),
      });

      const data = await response.json();

      setApiConnected(true);

      if (!response.ok) {
        const detail =
          typeof data?.detail === "string"
            ? data.detail
            : "Unable to process your request.";

        const errorMessage: ChatMessage = {
          id: createMessageId(),

          type: "bot",

          text: detail,

          isError: true,

          timestamp: getCurrentTime(),
        };

        setMessages((previous) => [
          ...previous,
          errorMessage,
        ]);

        return;
      }

      const chatData: ChatResponse = data;

      const botMessage: ChatMessage = {
        id: createMessageId(),

        type: "bot",

        text: chatData.answer,

        sources: chatData.sources ?? [],

        timestamp: getCurrentTime(),
      };

      setMessages((previous) => [
        ...previous,
        botMessage,
      ]);
    } catch {
      setApiConnected(false);

      setMessages((previous) => [
        ...previous,

        {
          id: createMessageId(),

          type: "bot",

          text:
            "I couldn't connect to the MediBot API. " +
            "Please make sure the FastAPI server is running.",

          isError: true,

          timestamp: getCurrentTime(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  /* =========================================================
     ENTER TO SEND
  ========================================================= */

  function handleKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      sendQuestion();
    }
  }

  /* =========================================================
     LOGIN PAGE
  ========================================================= */

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">

        <div className="w-full max-w-md">

          {/* Main Logo */}

          <div className="mb-7 flex justify-center">
            <MediBotLogo />
          </div>

          {/* Login Card */}

          <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">

            <div className="mb-6">

              <h2 className="text-xl font-semibold text-slate-900">
                Welcome back
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                Sign in to access MediBot.
              </p>

            </div>

            <form
              onSubmit={handleLogin}
              className="space-y-5"
            >

              <div>

                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Username
                </label>

                <input
                  value={username}
                  onChange={(event) =>
                    setUsername(event.target.value)
                  }
                  placeholder="Enter your username"
                  required
                  className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />

              </div>

              <div>

                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Password
                </label>

                <input
                  type="password"
                  value={password}
                  onChange={(event) =>
                    setPassword(event.target.value)
                  }
                  placeholder="Enter your password"
                  required
                  className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />

              </div>

              {loginError && (

                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {loginError}
                </div>

              )}

              <button
                type="submit"
                disabled={loginLoading}
                className="w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              >

                {loginLoading
                  ? "Signing in..."
                  : "Sign in"}

              </button>

            </form>

          </div>

          {/* API Status */}

          <div className="mt-5 flex items-center justify-center gap-2 text-xs text-slate-500">

            <span
              className={`h-2 w-2 rounded-full ${
                apiConnected
                  ? "bg-emerald-500"
                  : "bg-red-400"
              }`}
            />

            {apiConnected
              ? "MediBot API connected"
              : "MediBot API unavailable"}

          </div>

        </div>

      </main>
    );
  }

  /* =========================================================
     CHAT APP
  ========================================================= */

  const suggestions =
    ROLE_SUGGESTIONS[role] ?? [];

  return (
    <main className="h-screen overflow-hidden bg-white text-slate-900">

      <div className="flex h-full">

        {/* ==================================================
            SIDEBAR
        ================================================== */}

        <aside className="flex w-[320px] shrink-0 flex-col border-r border-slate-200 bg-slate-50">

          {/* Branding */}

          <div className="border-b border-slate-200 px-6 py-5">

            <MediBotLogo compact />

            <p className="ml-[84px] mt-1 text-xs leading-5 text-slate-500">
              AI Assistant for MediAssist
              <br />
              Health Network
            </p>

          </div>

          <div className="flex-1 overflow-y-auto px-5 py-5">

            {/* Profile */}

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">

              <div className="flex items-center gap-4">

                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-xl">
                  {profile.icon}
                </div>

                <div className="min-w-0">

                  <div className="truncate font-semibold text-slate-900">
                    {profile.name}
                  </div>

                  <div className="truncate text-sm text-slate-500">
                    @{username}
                  </div>

                </div>

              </div>

              <div className="mt-4">

                <span className="inline-flex rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">

                  {formatRole(role)}

                </span>

              </div>

            </section>

            {/* Collections */}

            <section className="mt-7">

              <div className="mb-3 flex items-center justify-between">

                <h2 className="text-sm font-semibold text-slate-900">
                  Accessible Collections
                </h2>

                <span
                  title="Collections available for your role"
                  className="flex h-5 w-5 items-center justify-center rounded-full border border-slate-300 text-xs text-slate-500"
                >
                  i
                </span>

              </div>

              <div className="space-y-2">

                {collections.map((collection) => {

                  const details =
                    COLLECTION_DETAILS[
                      collection.toLowerCase()
                    ];

                  return (

                    <div
                      key={collection}
                      className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 transition hover:border-blue-200 hover:bg-blue-50"
                    >

                      <span className="text-lg">
                        {details?.icon ?? "📄"}
                      </span>

                      <span className="text-sm font-medium text-slate-700">
                        {details?.label ??
                          formatRole(collection)}
                      </span>

                    </div>

                  );
                })}

              </div>

            </section>

            {/* RBAC Info */}

            <section className="mt-7 rounded-xl border border-blue-100 bg-blue-50 p-4">

              <div className="flex gap-3">

                <span className="text-lg">
                  🔐
                </span>

                <div>

                  <p className="text-sm font-semibold text-blue-900">
                    Role-based access
                  </p>

                  <p className="mt-1 text-xs leading-5 text-blue-700">
                    MediBot only retrieves information
                    available to your authorised role.
                  </p>

                </div>

              </div>

            </section>

          </div>

          {/* Logout */}

          <div className="border-t border-slate-200 p-5">

            <button
              onClick={handleLogout}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
            >

              <span>↪</span>

              Logout

            </button>

          </div>

        </aside>

        {/* ==================================================
            MAIN CHAT AREA
        ================================================== */}

        <section className="flex min-w-0 flex-1 flex-col bg-white">

          {/* Header */}

          <header className="border-b border-slate-200 px-8 py-5">

            <div className="flex items-center justify-between gap-6">

              <div>

                <h2 className="text-2xl font-bold tracking-tight text-slate-900">

                  Hello, {profile.name} 👋

                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  {ROLE_SUBTITLES[role] ??
                  "Ask MediBot about information available to your role."}
                </p>

              </div>

              <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 shadow-sm">

                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    apiConnected
                      ? "bg-emerald-500"
                      : "bg-red-400"
                  }`}
                />

                {apiConnected
                  ? "Connected"
                  : "Disconnected"}

              </div>

            </div>

          </header>

          {/* Suggestions */}

          {messages.length <= 1 && (

            <section className="border-b border-slate-100 px-8 py-5">

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">

                <div className="mb-4 flex items-center gap-2">

                  <span>💡</span>

                  <h3 className="text-sm font-semibold text-slate-900">
                    Try asking...
                  </h3>

                </div>

                <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">

                  {suggestions.map((suggestion) => (

                    <button
                      key={suggestion}
                      onClick={() =>
                        sendQuestion(suggestion)
                      }
                      disabled={loading}
                      className="rounded-xl border border-slate-200 bg-white px-4 py-4 text-left text-sm leading-6 text-blue-900 shadow-sm transition hover:border-blue-300 hover:bg-blue-50 disabled:opacity-50"
                    >

                      {suggestion}

                    </button>

                  ))}

                </div>

              </div>

            </section>

          )}

          {/* ==================================================
              CHAT MESSAGES
          ================================================== */}

          <div className="flex-1 overflow-y-auto px-8 py-8">

            <div className="mx-auto max-w-5xl space-y-7">

              {messages.map((message) => {

                /* USER MESSAGE */

                if (message.type === "user") {

                  return (

                    <div
                      key={message.id}
                      className="flex justify-end"
                    >

                      <div className="flex max-w-[78%] items-start gap-3">

                        <div className="text-right">

                          <div className="rounded-2xl rounded-tr-md border border-blue-100 bg-blue-50 px-5 py-4 text-left text-sm leading-7 text-slate-900">

                            {message.text}

                          </div>

                          {message.timestamp && (

                            <div className="mt-2 text-xs text-slate-400">

                              {message.timestamp}

                            </div>

                          )}

                        </div>

                        <UserAvatar />

                      </div>

                    </div>

                  );
                }

                /* BOT MESSAGE */

                return (

                  <div
                    key={message.id}
                    className="flex justify-start"
                  >

                    <div className="flex max-w-[82%] items-start gap-3">

                      <BotAvatar />

                      <div>

                        <div
                          className={`rounded-2xl rounded-tl-md border px-5 py-4 shadow-sm ${
                            message.isError
                              ? "border-red-200 bg-red-50"
                              : "border-slate-200 bg-white"
                          }`}
                        >

                          {/* RBAC / Error */}

                          {message.isError && (

                            <div className="mb-3 flex items-center gap-2 font-semibold text-red-700">

                              <span>🔒</span>

                              Access restricted

                            </div>

                          )}

                          {/* Answer */}

                          <div
                            className={`whitespace-pre-wrap text-sm leading-7 ${
                              message.isError
                                ? "text-red-700"
                                : "text-slate-800"
                            }`}
                          >

                            {message.text}

                          </div>

                          {/* Sources */}

                          {!message.isError &&
                            message.sources &&
                            message.sources.length > 0 && (

                              <div className="mt-5 border-t border-slate-200 pt-4">

                                <div className="mb-3 flex items-center gap-2">

                                  <span>📄</span>

                                  <span className="text-sm font-semibold text-slate-900">
                                    Sources
                                  </span>

                                </div>

                                <div className="space-y-2">

                                  {message.sources.map(
                                    (source, index) => (

                                      <div
                                        key={`${source.source_document}-${index}`}
                                        className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"
                                      >

                                        <div className="flex flex-wrap items-start justify-between gap-3">

                                          <div className="min-w-0">

                                            <div className="break-all text-sm font-semibold text-blue-700">

                                              {source.source_document}

                                            </div>

                                            <div className="mt-1 text-xs leading-5 text-slate-500">

                                              {source.section_title
                                                ? `Section: ${source.section_title}`
                                                : "Document source"}

                                            </div>

                                          </div>

                                          <span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">

                                            {formatRole(
                                              source.collection
                                            )}

                                          </span>

                                        </div>

                                      </div>

                                    )
                                  )}

                                </div>

                              </div>

                            )}

                        </div>

                        {message.timestamp && (

                          <div className="mt-2 text-xs text-slate-400">

                            {message.timestamp}

                          </div>

                        )}

                      </div>

                    </div>

                  </div>

                );
              })}

              {/* Loading Bubble */}

              {loading && (

                <div className="flex justify-start">

                  <div className="flex items-start gap-3">

                    <BotAvatar />

                    <div className="rounded-2xl rounded-tl-md border border-slate-200 bg-white px-5 py-4 shadow-sm">

                      <div className="flex items-center gap-3 text-sm text-slate-500">

                        <div className="flex gap-1">

                          <span className="h-2 w-2 animate-bounce rounded-full bg-blue-400 [animation-delay:-0.3s]" />

                          <span className="h-2 w-2 animate-bounce rounded-full bg-blue-400 [animation-delay:-0.15s]" />

                          <span className="h-2 w-2 animate-bounce rounded-full bg-blue-400" />

                        </div>

                        MediBot is searching...

                      </div>

                    </div>

                  </div>

                </div>

              )}

              <div ref={messagesEndRef} />

            </div>

          </div>

          {/* ==================================================
              CHAT INPUT
          ================================================== */}

          <footer className="border-t border-slate-200 bg-white px-8 py-5">

            <div className="mx-auto max-w-5xl">

              <div className="flex items-end gap-3 rounded-2xl border border-slate-300 bg-white p-3 shadow-sm transition focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100">

                <textarea
                  value={question}
                  onChange={(event) =>
                    setQuestion(event.target.value)
                  }
                  onKeyDown={handleKeyDown}
                  rows={1}
                  disabled={loading}
                  placeholder="Type your medical question..."
                  className="max-h-32 min-h-[44px] flex-1 resize-none bg-transparent px-2 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
                />

                <button
                  onClick={() => sendQuestion()}
                  disabled={
                    !question.trim() ||
                    loading
                  }
                  className="flex h-11 items-center gap-2 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                >

                  <svg
                    width="17"
                    height="17"
                    viewBox="0 0 24 24"
                    fill="none"
                  >

                    <path
                      d="M22 2L11 13"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />

                    <path
                      d="M22 2L15 22L11 13L2 9L22 2Z"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinejoin="round"
                    />

                  </svg>

                  Send

                </button>

              </div>

              <p className="mt-2 text-center text-xs text-slate-400">
                MediBot answers using information available to your authorised role.

              </p>

            </div>

          </footer>

        </section>

      </div>

    </main>
  );
}