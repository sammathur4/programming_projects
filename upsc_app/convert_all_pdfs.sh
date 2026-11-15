#!/bin/bash
# PDF to TXT Converter with Tracking

SOURCE_DIR="/media/saksham/80645C95645C9030/saksham/EXAM/01 upsc sociology 2027"
LOG_DIR="/media/saksham/phone data/programming_projects/upsc_app/pdf_conversion_logs"
TRACKER="$LOG_DIR/conversion_tracker.csv"
WORKERS=16

mkdir -p "$LOG_DIR"

# Initialize tracker if doesn't exist
if [ ! -f "$TRACKER" ]; then
    echo "pdf_path,txt_path,status,size_kb,converted_at,error" > "$TRACKER"
fi

# Create temp list of PDFs
find "$SOURCE_DIR" -name "*.pdf" -type f > "$LOG_DIR/all_pdfs.txt"
TOTAL=$(wc -l < "$LOG_DIR/all_pdfs.txt")

echo "Found $TOTAL PDFs. Starting conversion with $WORKERS workers..."
echo "Tracker: $TRACKER"
echo "Logs: $LOG_DIR"

# Function to check if already done
is_done() {
    local pdf="$1"
    local txt="${pdf%.pdf}.txt"
    if [ -f "$txt" ] && [ -s "$txt" ]; then
        return 0
    fi
    return 1
}

# Process in parallel
cat "$LOG_DIR/all_pdfs.txt" | while read -r pdf; do
    txt="${pdf%.pdf}.txt"
    if [ -f "$txt" ] && [ -s "$txt" ]; then
        size_kb=$(du -k "$txt" 2>/dev/null | awk '{print $1}')
        # Check if already tracked
        if ! grep -qF "$pdf" "$TRACKER"; then
            echo "\"$pdf\",\"$txt\",\"DONE\",\"$size_kb\",\"$(date -Iseconds)\",\"\"" >> "$TRACKER"
        fi
        continue
    fi
    echo "$pdf"
done | xargs -P $WORKERS -I{} sh -c '
pdf="{}"
txt="${pdf%.pdf}.txt"
logfile="/tmp/pdfconv_$$.log"
if timeout 300 pdftotext -layout "$pdf" "$txt" > "$logfile" 2>&1; then
    if [ -f "$txt" ] && [ -s "$txt" ]; then
        size_kb=$(du -k "$txt" 2>/dev/null | awk "{print \$1}")
        echo "\"$pdf\",\"$txt\",\"DONE\",\"$size_kb\",\"$(date -Iseconds)\",\"\"" >> '"$TRACKER"'
    else
        # Try without layout
        rm -f "$txt"
        if timeout 300 pdftotext "$pdf" "$txt" > "$logfile" 2>&1 && [ -s "$txt" ]; then
            size_kb=$(du -k "$txt" 2>/dev/null | awk "{print \$1}")
            echo "\"$pdf\",\"$txt\",\"DONE\",\"$size_kb\",\"$(date -Iseconds)\",\"\"" >> '"$TRACKER"'
        else
            echo "\"$pdf\",\"$txt\",\"IMPOSSIBLE_SCANNED_OR_ENCRYPTED\",\"0\",\"$(date -Iseconds)\",\"$(cat $logfile | tr \",\" \" \" | head -c 100)\"" >> '"$TRACKER"'
        fi
    fi
else
    echo "\"$pdf\",\"$txt\",\"TIMEOUT_OR_ERROR\",\"0\",\"$(date -Iseconds)\",\"TIMEOUT\"" >> '"$TRACKER"'
fi
rm -f "$logfile"
'

echo "Conversion complete. Check tracker: $TRACKER"
echo "Summary:"
echo "  DONE: $(grep -c ',\"DONE\",' $TRACKER)"
echo "  IMPOSSIBLE: $(grep -c ',\"IMPOSSIBLE' $TRACKER)"
echo "  PENDING/ERROR: $(grep -c ',\"TIMEOUT\|ERROR' $TRACKER)"
