#!/usr/bin/env bash

# Colors and formatting
RESET='\x1b[0m'
BOLD='\x1b[1m'
DIM='\x1b[2m'
CYAN='\x1b[36m'
GREEN='\x1b[32m'
YELLOW='\x1b[33m'
BLUE='\x1b[34m'
GRAY='\x1b[90m'

# Box drawing characters
TL='╭' TR='╮' BL='╰' BR='╯'
H='─' V='│'

# Get terminal dimensions
COLS=$(tput cols)  # 80
LINES=$(tput lines)  # 22

# echo "${COLS}x${LINES} terminal detected."
# sleep 1

# Clear screen and hide cursor
printf '\x1b[2J\x1b[?25l'

repeat() {
    local str=$1
    local num=$2
    local result=""
    for ((i=0; i<num; i++)); do
        result+="$str"
    done
    echo -n "$result"
}

center() {
    local text="$1"
    local width="$2"
    local left_padding=$(( (width - ${#text}) / 2 ))
    local right_padding=$(( width - ${#text} - left_padding ))
    printf "%*s%s%*s" "$left_padding" "" "$text" "$right_padding" ""
}

# Function to draw header box
draw_header() {
    printf '\x1b[1;1H'

    # Top border
    printf "${CYAN}${TL}${H}${H}${H} Claude Code v2.0.76 "
    printf "%*s" $((COLS - 26)) | tr ' ' "${H}"
    printf "${TR}${RESET}\n"

    # Content lines
    printf "${CYAN}${V}${RESET}%*s${CYAN}${V}${RESET}%-*s${CYAN}${V}${RESET}\n" 38 "" 39 " Tips for getting started"
    printf "${CYAN}${V}${RESET}${BOLD}%*s${RESET}${CYAN}${V}${RESET}%-*s${CYAN}${V}${RESET}\n" 38 "$(center "Welcome back, Nilton!" 38)" 39 " Run /init to create a CLAUDE.md file"
    printf "${CYAN}${V}${RESET}%*s${CYAN}${V}${RESET} %*s ${CYAN}${V}${RESET}\n" 38 "" 39 $(repeat "$H" 37)
    printf "${CYAN}${V}${RESET}${YELLOW}%*s${RESET}${CYAN}${V}${RESET}%*s${CYAN}${V}${RESET}\n" 38 "$(center "* ▐▛███▜▌ *" 38)" 39 " Recent activity"
    printf "${CYAN}${V}${RESET}${YELLOW}%*s${RESET}${CYAN}${V}${RESET}%*s${CYAN}${V}${RESET}\n" 38 "$(center "* ▝▜█████▛▘ *" 38)" 39 " No recent activity"
    printf "${CYAN}${V}${RESET}${YELLOW}%*s${RESET}${CYAN}${V}${RESET}%*s${CYAN}${V}${RESET}\n" 38 "$(center "*  ▘▘ ▝▝  *" 38)" 39 ""
    printf "${CYAN}${V}${RESET}%*s${CYAN}${V}${RESET}%*s${CYAN}${V}${RESET}\n" 38 "" 39 ""
    printf "${CYAN}${V}${RESET}${DIM}%-*s${RESET} ${CYAN}${V}${RESET}%*s${CYAN}${V}${RESET}\n" 38 " Opus 4.5 · Claude Max" 39 ""

    # Bottom border
    printf "${CYAN}${BL}"
    printf "%*s" $((COLS - 2)) | tr ' ' "${H}"
    printf "${BR}${RESET}\n"
}

# Function to type text with delay
type_text() {
    local text="$1"
    local delay="${2:-0.05}"

    for ((i=0; i<${#text}; i++)); do
        printf "%s" "${text:$i:1}"
        sleep "$delay"
    done
}

# Function to draw separator
draw_separator() {
    printf "${GRAY}"
    printf "%*s\n" "$COLS" | tr ' ' '─'
    printf "${RESET}"
}

# Setup scrolling region (leave space for header)
printf "\x1b[1;20r"

# Draw initial header
draw_header

# Position at the bottom
printf "\x1b[21;1H"
draw_separator
printf "\x1b[22;1H"

sleep 1

# User prompt
printf "\n${GREEN}>${RESET} "
sleep 0.5
type_text "Master, should programmers fear AI?" 0.08
sleep 0.5
printf "\x1b[2K"
printf "\n${GREEN}>${RESET} "

printf "\x1b[19;1H"
printf "\n${GREEN}>${RESET} Master, should programmers fear AI?\n\n"

sleep 0.5

# Status line with spinner animation
printf "${BLUE}⏺${RESET} ${BOLD}master-programmer:guru${RESET}${DIM}(AI and programmers wisdom)${RESET}\n"
sleep 0.5
printf "  ${GRAY}⎿${RESET}  "

# Simulate thinking
for i in {1..8}; do
    printf "."
    sleep 0.5
done

printf " ${GREEN}Done${RESET} ${DIM}(0 tool uses · 14.0k tokens · 12s)${RESET}\n\n"

sleep 1

# Response header
printf "${BLUE}⏺${RESET} ${BOLD}The Koan of the Silicon Apprentice${RESET}\n\n"
printf "  ${GRAY}---${RESET}\n"

sleep 0.5

# Stream the response
response=(
    "  A young programmer came before the Master, trembling. ${CYAN}\"Master,\"${RESET} he said,"
    "  ${CYAN}\"I have heard that the machines grow wise. Soon they will write all code,"
    "  and we shall be cast out into the marketplace, forced to become product"
    "  managers.\"${RESET}"
    ""
    "  The Master closed his eyes for a long moment. When he opened them, he"
    "  asked: ${YELLOW}\"Tell me, does the hammer fear the nail gun?\"${RESET}"
    ""
    "  ${CYAN}\"No, Master,\"${RESET} said the programmer, confused."
    ""
    "  ${YELLOW}\"And yet,\"${RESET} continued the Master, ${YELLOW}\"I have seen many a carpenter's thumb"
    "  saved by the nail gun, and many more thumbs crushed by improper use of the"
    "  nail gun. The tool does not replace the craftsman. It merely changes which"
    "  mistakes he is capable of making.\"${RESET}"
    ""
    "  The programmer pondered this. ${CYAN}\"But Master, what if the AI becomes so"
    "  powerful it needs no human guidance?\"${RESET}"
    ""
    "  The Master gestured to his screen, where an AI had confidently generated a"
    "  function that sorted an array by randomly shuffling it until it happened"
    "  to be sorted. ${YELLOW}\"When that day comes,\"${RESET} said the Master, ${YELLOW}\"wake me from my"
    "  grave and show me. Until then, someone must still ask the correct"
    "  question, recognize the incorrect answer, and git revert when the"
    "  deployment catches fire.\"${RESET}"
    ""
    "  ${GRAY}---${RESET}"
    "  ${DIM}Thus it is written: The wise programmer fears not the tool, but the"
    "  manager who wields it without understanding. For AI is like a very fast"
    "  intern—impressive in its speed, confident in its errors, and requiring"
    "  supervision lest it drop the production database.${RESET}"
)

for line in "${response[@]}"; do
    echo -e "$line"
    sleep 1
done

printf "\n"

for i in {1..10}; do
    printf "\x1b[22;1H"
    printf "\n${GREEN}>${RESET} _"
    sleep 0.2
    printf "\x1b[22;1H"
    printf "\n${GREEN}>${RESET}  "
    sleep 0.2
done

sleep 5

printf "\x1b[2K"

sleep 0.2

# Cleanup
printf '\x1b[r'  # Reset scroll region
printf '\x1b[?25h'  # Show cursor

clear
