import {
    getDocument,
    GlobalWorkerOptions
} from "/static/pdfjs/pdf.mjs";

GlobalWorkerOptions.workerSrc = "/static/pdfjs/pdf.worker.mjs";

const viewer = document.getElementById("controlled-pdf-viewer");

if (!viewer) {
    throw new Error("Controlled PDF viewer container not found.");
}

const pdfUrl = viewer.dataset.pdfUrl;

if (!pdfUrl) {
    throw new Error("Controlled PDF URL not provided.");
}

const canvas = document.getElementById("controlled-pdf-canvas");
const canvasContext = canvas.getContext("2d");

const pageNumberElement = document.getElementById("pdf-page-number");
const pageCountElement = document.getElementById("pdf-page-count");

const previousButton = document.getElementById("pdf-previous");
const nextButton = document.getElementById("pdf-next");
const zoomOutButton = document.getElementById("pdf-zoom-out");
const zoomInButton = document.getElementById("pdf-zoom-in");

let pdfDocument = null;
let currentPage = 1;
let scale = 1.25;
let rendering = false;
let pendingPage = null;

async function loadPdf() {
    try {
        const loadingTask = getDocument({
            url: pdfUrl,
            disableAutoFetch: false,
            disableStream: false
        });

        pdfDocument = await loadingTask.promise;

        pageCountElement.textContent = pdfDocument.numPages;

        await renderPage(currentPage);

        updateControls();

    } catch (error) {
        console.error("Controlled PDF viewer error:", error);

        viewer.innerHTML = `
            <div class="controlled-pdf-error">
                Unable to display this document.
                Please contact Compliance.
            </div>
        `;
    }
}

async function renderPage(pageNumber) {
    if (rendering) {
        pendingPage = pageNumber;
        return;
    }

    rendering = true;

    try {
        const page = await pdfDocument.getPage(pageNumber);

        const viewport = page.getViewport({
            scale: scale
        });

        const outputScale = window.devicePixelRatio || 1;

        canvas.width = Math.floor(viewport.width * outputScale);
        canvas.height = Math.floor(viewport.height * outputScale);

        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        const transform =
            outputScale !== 1
                ? [outputScale, 0, 0, outputScale, 0, 0]
                : null;

        await page.render({
            canvasContext: canvasContext,
            transform: transform,
            viewport: viewport
        }).promise;

        currentPage = pageNumber;

        pageNumberElement.textContent = currentPage;

        updateControls();

    } catch (error) {
        console.error("PDF page rendering error:", error);
    } finally {
        rendering = false;

        if (pendingPage !== null) {
            const nextPage = pendingPage;
            pendingPage = null;
            renderPage(nextPage);
        }
    }
}

function updateControls() {
    previousButton.disabled = currentPage <= 1;
    nextButton.disabled =
        !pdfDocument || currentPage >= pdfDocument.numPages;
}

previousButton.addEventListener("click", function () {
    if (currentPage > 1) {
        renderPage(currentPage - 1);
    }
});

nextButton.addEventListener("click", function () {
    if (pdfDocument && currentPage < pdfDocument.numPages) {
        renderPage(currentPage + 1);
    }
});

zoomOutButton.addEventListener("click", function () {
    scale = Math.max(0.75, scale - 0.15);
    renderPage(currentPage);
});

zoomInButton.addEventListener("click", function () {
    scale = Math.min(3, scale + 0.15);
    renderPage(currentPage);
});

document.addEventListener("keydown", function (event) {
    const key = event.key.toLowerCase();

    if (
        (event.ctrlKey || event.metaKey) &&
        ["s", "p", "u"].includes(key)
    ) {
        event.preventDefault();
        event.stopPropagation();
    }

    if (
        event.ctrlKey &&
        event.shiftKey &&
        ["i", "j", "s"].includes(key)
    ) {
        event.preventDefault();
        event.stopPropagation();
    }

    if (key === "printscreen") {
        event.preventDefault();
    }
});

viewer.addEventListener("contextmenu", function (event) {
    event.preventDefault();
});

viewer.addEventListener("dragstart", function (event) {
    event.preventDefault();
});

loadPdf();