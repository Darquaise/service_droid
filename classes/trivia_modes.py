# Posting modes for trivia channels.
# Only TIMED is currently user-selectable; AI / AI_TIMED are reserved for future use.
MODE_TIMED = "TIMED"        # post question, reveal answer after `response` seconds
MODE_AI = "AI"              # during the response window, AI reacts with ✅ to every correct reply (reaction removed after 10s)
MODE_AI_TIMED = "AI_TIMED"  # at the end of the response window, AI reviews all replies sent since the question and posts the list of users who answered correctly

MODE_DISPLAY = {
    MODE_TIMED: "Timed answer reveal",
    MODE_AI: "AI live reactions",
    MODE_AI_TIMED: "AI end-of-round summary",
}

SELECTABLE_MODES = (MODE_TIMED,)


# Question-picking strategies.
ORDER_RANDOM = "random"
ORDER_SEQUENTIAL = "sequential"

ORDER_DISPLAY = {
    ORDER_RANDOM: "Random",
    ORDER_SEQUENTIAL: "Sequential (in order)",
}

ALL_ORDERS = (ORDER_RANDOM, ORDER_SEQUENTIAL)