"""Laboratory 3 — Fundamental Software Design Principles.

Runnable Python examples for the laboratory's redesign exercises.
Answers to all 39 paper/theory questions are included as comments at the
end of this file, because the original worksheet explicitly requests no
programming for many of its questions.

Run: python Laboratory_3_Solutions.py
Tests: python -m unittest Laboratory_3_Solutions.py
Requires: Python 3.10+ (standard library only).
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
import tempfile
import unittest
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Callable, Protocol


# -----------------------------------------------------------------------------
# PART A (Questions 1–5) — Module boundaries and information hiding
# -----------------------------------------------------------------------------

class Parking:
    """Q4–5: keep space representation and pricing inside Parking."""

    def __init__(self, capacity: int = 50) -> None:
        if capacity <= 0:
            raise ValueError("Parking capacity must be positive")
        self._capacity = capacity
        self._occupied: dict[int, tuple[str, str]] = {}
        self._prices = {"car": Decimal("5000"), "bus": Decimal("15000")}

    def has_free_place(self) -> bool:
        return len(self._occupied) < self._capacity

    def park(self, car_number: str, vehicle_type: str = "car") -> int:
        if vehicle_type not in self._prices:
            raise ValueError("Unknown vehicle type")
        if not self.has_free_place():
            raise ValueError("Parking is full")
        for number in range(self._capacity):
            if number not in self._occupied:
                self._occupied[number] = (car_number, vehicle_type)
                return number
        raise RuntimeError("Inconsistent parking state")

    def leave(self, place_number: int) -> None:
        if place_number not in self._occupied:
            raise ValueError("Place is not occupied")
        del self._occupied[place_number]

    def calculate_cost(self, vehicle_type: str, hours: int) -> Decimal:
        if hours < 0:
            raise ValueError("Hours cannot be negative")
        return self._prices[vehicle_type] * hours

    def available_place_numbers(self) -> tuple[int, ...]:
        """Read-only snapshot; the caller never obtains self._occupied."""
        return tuple(i for i in range(self._capacity) if i not in self._occupied)


# Q1: auth, screen, and reminder should be separate. Q2: five cinema jobs.
@dataclass(frozen=True)
class FilmSession:
    session_id: str
    film: str
    seat_count: int


class SessionCatalog:
    def __init__(self) -> None:
        self._sessions: dict[str, FilmSession] = {}

    def add(self, session: FilmSession) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> FilmSession:
        return self._sessions[session_id]


class SeatRegistry:
    def __init__(self) -> None:
        self._sold_seats: dict[str, set[int]] = {}

    def free_seats(self, session: FilmSession) -> tuple[int, ...]:
        sold = self._sold_seats.get(session.session_id, set())
        return tuple(i for i in range(1, session.seat_count + 1) if i not in sold)

    def reserve(self, session: FilmSession, seat_number: int) -> None:
        if seat_number not in self.free_seats(session):
            raise ValueError("Seat unavailable")
        self._sold_seats.setdefault(session.session_id, set()).add(seat_number)


class TicketPrinter:
    def print_ticket(self, session: FilmSession, seat_number: int) -> str:
        # A real printer implementation could encode this payload as a QR code.
        return f"TICKET | {session.film} | seat={seat_number} | QR:{session.session_id}:{seat_number}"


class TicketSales:
    def __init__(self, catalog: SessionCatalog, seats: SeatRegistry, printer: TicketPrinter) -> None:
        self._catalog = catalog
        self._seats = seats
        self._printer = printer
        self._sales: list[str] = []

    def sell(self, session_id: str, seat_number: int) -> str:
        session = self._catalog.get(session_id)
        self._seats.reserve(session, seat_number)
        self._sales.append(session_id)
        return self._printer.print_ticket(session, seat_number)

    def tickets_sold(self, session_id: str) -> int:
        return self._sales.count(session_id)


class SalesReport:
    def __init__(self, catalog: SessionCatalog, sales: TicketSales) -> None:
        self._catalog, self._sales = catalog, sales

    def sales_for_session(self, session_id: str) -> tuple[str, int]:
        return self._catalog.get(session_id).film, self._sales.tickets_sold(session_id)


# -----------------------------------------------------------------------------
# PART B (Questions 6–10) — Abstraction
# -----------------------------------------------------------------------------

class Counter:
    """Q9: same public interface, dictionary implementation (version 2)."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def add(self, word: str) -> None:
        self._counts[word] = self._counts.get(word, 0) + 1

    def count(self, word: str) -> int:
        return self._counts.get(word, 0)


class ExamTimer:
    """Q10: enough public methods, without exposing internal state."""

    def __init__(self, now: Callable[[], float]) -> None:
        self._now = now
        self._deadline: float | None = None
        self._stopped = True

    def start(self, minutes: float) -> None:
        if minutes <= 0:
            raise ValueError("Duration must be positive")
        self._deadline = self._now() + minutes * 60
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def seconds_left(self) -> int:
        if self._stopped or self._deadline is None:
            return 0
        return max(0, int(self._deadline - self._now()))

    def is_finished(self) -> bool:
        return self.seconds_left() == 0


# -----------------------------------------------------------------------------
# PART C (Questions 11–15) — Cohesion
# -----------------------------------------------------------------------------

def is_leap_year(year: int) -> bool:
    """Q11(c): functional cohesion: one clear job."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


@dataclass(frozen=True)
class InvoiceLine:
    product: str
    quantity: int
    unit_price: Decimal


class Invoice:
    """Q13: invoice data/calculation responsibility only."""

    def __init__(self) -> None:
        self._lines: list[InvoiceLine] = []

    def add_line(self, product: str, qty: int, unit_price: Decimal) -> None:
        self._lines.append(InvoiceLine(product, qty, unit_price))

    def total(self) -> Decimal:
        return sum((line.quantity * line.unit_price for line in self._lines), Decimal(0))


class InvoicePDFExporter:
    def to_pdf(self, invoice: Invoice) -> bytes:
        # Illustrative output only; does not claim to be a real PDF document.
        return f"Invoice total: {invoice.total()}".encode("utf-8")


class InvoiceEmailSender:
    def __init__(self, send: Callable[[str, str], None]) -> None:
        self._send = send

    def email_to_customer(self, address: str, invoice: Invoice) -> None:
        self._send(address, f"Invoice total: {invoice.total()}")


class InvoiceRepository:
    def __init__(self) -> None:
        self._invoices: list[Invoice] = []

    def save(self, invoice: Invoice) -> None:
        self._invoices.append(invoice)


# -----------------------------------------------------------------------------
# PART D (Questions 16–20) — Low coupling; dependency injection
# -----------------------------------------------------------------------------

def send_sms(phone: str, text: str, gateway: Callable[[str, str], None]) -> None:
    """Q17(1): data coupling: pass the needed phone rather than a User."""
    gateway(phone, text)


def format_price_short(amount: Decimal) -> str:
    """Q17(2): no style flag / no control coupling."""
    return f"{amount} sum"


def format_price_long(amount: Decimal) -> str:
    return f"{amount:,} UZS"


class Session:
    """Q17(3): owns logged-in user without a public global."""

    def __init__(self) -> None:
        self._current_user: str | None = None

    def login(self, user: str) -> None:
        self._current_user = user

    def can_delete(self) -> bool:
        return self._current_user == "admin"


class UserDatabase:
    """Q17(4): callers use operations, not db._connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def sales_rows(self) -> list[tuple]:
        return self._connection.execute("SELECT * FROM sales").fetchall()


class DatabaseSalesReport:
    def build(self, database: UserDatabase) -> list[tuple]:
        return database.sales_rows()


class MessageSender(Protocol):
    def send(self, destination: str, text: str) -> None: ...


class RecordingSender:
    """Test double; never sends an outside message."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, destination: str, text: str) -> None:
        self.messages.append((destination, text))


class NoopSender:
    def send(self, destination: str, text: str) -> None:
        pass


class AttendanceReport:
    """Q19: sender and destination are injected by the caller."""

    def __init__(self, sender: MessageSender, destination: str) -> None:
        self._sender, self._destination = sender, destination

    def send(self, text: str) -> None:
        self._sender.send(self._destination, text)


# -----------------------------------------------------------------------------
# PART E (Questions 21–24) — DRY, KISS, YAGNI, separation of concerns
# -----------------------------------------------------------------------------

MAX_STUDENTS = 30  # Q21(a): one source of truth


def can_enroll(current_count: int) -> bool:
    return current_count < MAX_STUDENTS


def is_adult(age: int) -> bool:
    return age >= 18  # Q21(b): simple rule (KISS)


def max_of_three(a: int, b: int, c: int) -> int:
    return max(a, b, c)  # Q21(e): simple rule (KISS)


def shipping_fee(weight_kg: Decimal) -> Decimal:
    return weight_kg * Decimal("2000")


def parking_fee(hours: int) -> Decimal:
    return Decimal(hours) * Decimal("2000")


# Q22: do NOT merge the last two functions; equal numbers encode distinct rules.
# Q23: messages.py for Uzbek strings is good design; a seven-language translation
# engine requested by nobody breaks YAGNI.


# -----------------------------------------------------------------------------
# PART F (Questions 25–29) — Dormitory laundry, fully working redesign
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Student:
    name: str
    telegram_id: str
    is_resident: bool


@dataclass(frozen=True)
class LaundryBooking:
    student_name: str
    machine: int
    hour: int
    mode: str
    price: Decimal


class LaundryPricing:
    """Owns all prices and discount rules; each constant appears once."""

    WASH_PRICE = Decimal("8000")
    DRY_ADDON = Decimal("6000")
    RESIDENT_DISCOUNT = Decimal("0.10")

    def price(self, mode: str, is_resident: bool) -> Decimal:
        if mode not in ("wash", "wash+dry"):
            raise ValueError("Unknown washing mode")
        amount = self.WASH_PRICE
        if mode == "wash+dry":
            amount += self.DRY_ADDON
        if is_resident:
            amount *= (Decimal(1) - self.RESIDENT_DISCOUNT)
        return amount


class LaundrySchedule:
    """Only schedule owns machine/hour availability (not a global STATUS)."""

    def __init__(self, machine_count: int = 6) -> None:
        self._machine_count = machine_count
        self._reserved: set[tuple[str, int, int]] = set()

    def is_available(self, day: str, machine: int, hour: int) -> bool:
        self._validate(machine, hour)
        return (day, machine, hour) not in self._reserved

    def reserve(self, day: str, machine: int, hour: int) -> None:
        if not self.is_available(day, machine, hour):
            raise ValueError("Machine is busy at that time")
        self._reserved.add((day, machine, hour))

    def release(self, day: str, machine: int, hour: int) -> None:
        self._reserved.discard((day, machine, hour))

    def _validate(self, machine: int, hour: int) -> None:
        if not 1 <= machine <= self._machine_count:
            raise ValueError("Machine must be between 1 and 6")
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")


class LaundryRepository:
    """SQLite is private to this class; WeeklyReport calls its public method."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._db = connection
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS laundry_bookings (
                id INTEGER PRIMARY KEY,
                student_name TEXT NOT NULL,
                machine INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                day TEXT NOT NULL,
                mode TEXT NOT NULL,
                price TEXT NOT NULL,
                UNIQUE(day, machine, hour)
            )
        """)
        self._db.commit()

    def save(self, booking: LaundryBooking, day: str) -> None:
        self._db.execute("""
            INSERT INTO laundry_bookings (student_name, machine, hour, day, mode, price)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (booking.student_name, booking.machine, booking.hour, day,
              booking.mode, str(booking.price)))
        self._db.commit()

    def used_hours(self, machine: int, day_prefix: str = "") -> int:
        result = self._db.execute("""
            SELECT COUNT(*) FROM laundry_bookings
            WHERE machine = ? AND day LIKE ?
        """, (machine, f"{day_prefix}%")).fetchone()
        return int(result[0])


class Laundry:
    """Orchestrator; each dependency has a single responsibility."""

    def __init__(self, schedule: LaundrySchedule, pricing: LaundryPricing,
                 repository: LaundryRepository, sender: MessageSender) -> None:
        self._schedule = schedule
        self._pricing = pricing
        self._repository = repository
        self._sender = sender

    def book(self, student: Student, machine: int, hour: int,
             mode: str, day: str) -> LaundryBooking:
        if not self._schedule.is_available(day, machine, hour):
            raise ValueError("Machine is busy")
        amount = self._pricing.price(mode, student.is_resident)
        booking = LaundryBooking(student.name, machine, hour, mode, amount)
        self._schedule.reserve(day, machine, hour)
        try:
            self._repository.save(booking, day)
        except Exception:
            self._schedule.release(day, machine, hour)
            raise
        self._sender.send(student.telegram_id,
                          f"Machine {machine} is yours on {day} at {hour}:00")
        return booking


class WeeklyReport:
    def __init__(self, repository: LaundryRepository) -> None:
        self._repository = repository

    def used_hours(self, machine: int, week_prefix: str) -> int:
        return self._repository.used_hours(machine, week_prefix)


class LaundryScreen:
    """Only UI prints the confirmation; business classes never print."""

    def __init__(self, laundry: Laundry) -> None:
        self._laundry = laundry

    def book_and_display(self, student: Student, machine: int, hour: int,
                         mode: str, day: str) -> None:
        try:
            result = self._laundry.book(student, machine, hour, mode, day)
        except ValueError as error:
            print(str(error))
            return
        print(f"Booked! Price: {result.price}")


# -----------------------------------------------------------------------------
# PART G (Questions 30–33) — Coupling in depth
# -----------------------------------------------------------------------------

class CurrencyPolicy:
    """Q30: controls currency and its rounding precision atomically."""

    def __init__(self, currency: str = "UZS") -> None:
        self._currency = ""
        self._step = Decimal("1")
        self.set_currency(currency)

    def set_currency(self, currency: str) -> None:
        steps = {"UZS": Decimal("1"), "USD": Decimal("0.01")}
        if currency not in steps:
            raise ValueError("Unsupported currency")
        self._currency, self._step = currency, steps[currency]

    def get_currency(self) -> str:
        return self._currency

    def round_amount(self, amount: Decimal) -> Decimal:
        return amount.quantize(self._step, rounding=ROUND_HALF_UP)

    def format_amount(self, amount: Decimal) -> str:
        return f"{self.round_amount(amount):f} {self._currency}"


def delivery_date(city: str, weight_kg: Decimal) -> str:
    """Q31: use just the two pieces of data needed, not the whole Order."""
    return f"Delivery planned for {city} ({weight_kg} kg)"


def schedule_delivery(city: str, weight_kg: Decimal) -> str:
    return delivery_date(city, weight_kg)


def confirm_delivery(message: str) -> str:
    return message


def checkout_delivery(city: str, weight_kg: Decimal) -> str:
    return confirm_delivery(schedule_delivery(city, weight_kg))


class BookLoans:
    """Q32: explicit dependency injection, simple when listeners are stable."""

    def __init__(self, on_fine_check: Callable[[str], None],
                 on_notify: Callable[[str], None],
                 on_stats: Callable[[str], None]) -> None:
        self._fine_check, self._notify, self._stats = on_fine_check, on_notify, on_stats

    def return_book(self, book_id: str) -> None:
        self._fine_check(book_id)
        self._notify(book_id)
        self._stats(book_id)


def discount_for_level(customer_level: str) -> Decimal:
    """Q33: pricing does not import Order, so dependency cycle is broken."""
    return Decimal("0.10") if customer_level == "gold" else Decimal("0")


# -----------------------------------------------------------------------------
# PART H (Questions 34–37) — DRY, KISS, YAGNI in depth
# -----------------------------------------------------------------------------

class PhoneNumbers:
    """Q34: one owner of country-specific phone validation/formatting."""

    def __init__(self, accepted_patterns: tuple[str, ...] = (r"\+998\d{9}",)) -> None:
        self._patterns = tuple(re.compile(rf"^(?:{pattern})$") for pattern in accepted_patterns)

    def is_valid(self, phone: str) -> bool:
        return any(pattern.fullmatch(phone) for pattern in self._patterns)

    def to_gateway_digits(self, phone: str) -> str:
        if not self.is_valid(phone):
            raise ValueError("Invalid phone number")
        return phone.removeprefix("+")

    def masked(self, phone: str) -> str:
        if not self.is_valid(phone):
            raise ValueError("Invalid phone number")
        return phone[:4] + "*" * max(0, len(phone) - 8) + phone[-4:]


# Q35: share subtotal only; avoid one function with four branch-controlling flags.
def subtotal(items: list[InvoiceLine]) -> Decimal:
    return sum((line.unit_price * line.quantity for line in items), Decimal(0))


def invoice_total(items: list[InvoiceLine]) -> Decimal:
    return (subtotal(items) * Decimal("1.12")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def refund_total(items: list[InvoiceLine]) -> Decimal:
    return -(subtotal(items) * Decimal("1.12"))


def quote_total(items: list[InvoiceLine]) -> Decimal:
    return subtotal(items)


class StudentNotFound(Exception):
    """Q37: storage returns a typed error, not translated presentation text."""


class StudentStore:
    def __init__(self, debt_by_id: dict[int, Decimal]) -> None:
        self._debts = debt_by_id.copy()

    def find_student(self, student_id: int) -> Decimal:
        if student_id not in self._debts:
            raise StudentNotFound(student_id)
        return self._debts[student_id]


@dataclass(frozen=True)
class CheckInResult:
    code: str
    room: str


class CheckInRules:
    def __init__(self, store: StudentStore) -> None:
        self._store = store

    def check_in(self, student_id: int, room: str) -> CheckInResult:
        try:
            debt = self._store.find_student(student_id)
        except StudentNotFound:
            return CheckInResult("STUDENT_NOT_FOUND", room)
        return CheckInResult("DEBT" if debt > 0 else "OK", room)


class CheckInScreen:
    def __init__(self, rules: CheckInRules) -> None:
        self._rules = rules

    def check_in_page(self, student_id: int, room: str) -> str:
        result = self._rules.check_in(student_id, room)
        if result.code == "OK":
            return f"<p class='green'>Welcome to room {result.room}</p>"
        if result.code == "DEBT":
            return "<p class='red'>Pay your debt first</p>"
        return "<p class='red'>Student not found</p>"


# -----------------------------------------------------------------------------
# PART I (Questions 38–39) — Library fines, fully working redesign
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Reader:
    name: str
    email: str
    card: str = "standard"


@dataclass(frozen=True)
class Book:
    title: str
    price: Decimal


@dataclass(frozen=True)
class FineEntry:
    reader_name: str
    book_title: str
    amount: Decimal


class FineCalculator:
    """Q39 design X: owns fine policy and only fine policy."""

    PER_DAY = Decimal("500")
    GOLD_MULTIPLIER = Decimal("0.50")

    def calculate(self, reader: Reader, book: Book, days_late: int) -> Decimal:
        if days_late <= 0:
            return Decimal(0)
        fine = Decimal(days_late) * self.PER_DAY
        if reader.card == "gold":
            fine *= self.GOLD_MULTIPLIER
        return min(fine, book.price)


class FineLedger:
    """One persistent source of truth; supports commas in book titles."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._db = connection
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS fines (
                id INTEGER PRIMARY KEY,
                reader_name TEXT NOT NULL,
                book_title TEXT NOT NULL,
                amount TEXT NOT NULL
            )
        """)
        self._db.commit()

    def add(self, entry: FineEntry) -> None:
        self._db.execute("INSERT INTO fines (reader_name, book_title, amount) VALUES (?, ?, ?)",
                         (entry.reader_name, entry.book_title, str(entry.amount)))
        self._db.commit()

    def total(self) -> Decimal:
        rows = self._db.execute("SELECT amount FROM fines").fetchall()
        return sum((Decimal(row[0]) for row in rows), Decimal(0))

    def export_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        for row in self._db.execute("SELECT reader_name, book_title, amount FROM fines"):
            writer.writerow(row)
        return output.getvalue()


class FineNotifier:
    def __init__(self, sender: MessageSender) -> None:
        self._sender = sender

    def send_fine(self, reader: Reader, book: Book, fine: Decimal) -> None:
        self._sender.send(reader.email, f"Fine for {book.title}: {fine}")


class Library:
    """Q39 design X: coordinates calculator, ledger and notifier."""

    def __init__(self, calculator: FineCalculator, ledger: FineLedger,
                 notifier: FineNotifier) -> None:
        self._calculator = calculator
        self._ledger = ledger
        self._notifier = notifier

    def return_book(self, reader: Reader, book: Book, days_late: int) -> Decimal:
        fine = self._calculator.calculate(reader, book, days_late)
        if fine > 0:
            self._ledger.add(FineEntry(reader.name, book.title, fine))
            self._notifier.send_fine(reader, book, fine)
        return fine

    def total_fines(self) -> Decimal:
        return self._ledger.total()


class MonthlyReport:
    def __init__(self, ledger: FineLedger) -> None:
        self._ledger = ledger

    def total(self) -> Decimal:
        return self._ledger.total()


def month_total_csv(csv_text: str) -> Decimal:
    """Q38: robust CSV parser for any title containing commas."""
    total = Decimal(0)
    for row in csv.reader(io.StringIO(csv_text)):
        if not row:
            continue
        total += Decimal(row[-1])
    return total


# -----------------------------------------------------------------------------
# Run examples (local only: no real SMS, Telegram, or e-mail is sent)
# -----------------------------------------------------------------------------

def main() -> None:
    parking = Parking(2)
    place = parking.park("01A123BC")
    print("Parking place:", place, "| free:", parking.available_place_numbers())

    counter = Counter()
    for word in ("apple", "banana", "apple"):
        counter.add(word)
    print("'apple' count:", counter.count("apple"))

    with sqlite3.connect(":memory:") as laundry_db:
        laundry_sender = RecordingSender()
        laundry_repository = LaundryRepository(laundry_db)
        laundry = Laundry(LaundrySchedule(), LaundryPricing(),
                          laundry_repository, laundry_sender)
        LaundryScreen(laundry).book_and_display(
            Student("Aziza", "demo_telegram_id", True), 3, 10,
            "wash+dry", "2026-10-21"
        )
        print("Machine 3 used hours:", WeeklyReport(laundry_repository).used_hours(3, "2026-10"))
        print("Messages recorded (not sent):", len(laundry_sender.messages))

    with sqlite3.connect(":memory:") as fines_db:
        fine_sender = RecordingSender()
        ledger = FineLedger(fines_db)
        library = Library(FineCalculator(), ledger, FineNotifier(fine_sender))
        fine = library.return_book(
            Reader("Malika", "demo@example.test", "gold"),
            Book("Algorithms, Part 1", Decimal("5000")),
            days_late=4,
        )
        print("Fine:", fine, "| monthly total:", MonthlyReport(ledger).total())
        print("Safe CSV export:", ledger.export_csv().strip())


class Lab3Tests(unittest.TestCase):
    def test_parking_hides_storage(self) -> None:
        parking = Parking(2)
        self.assertTrue(parking.has_free_place())
        place = parking.park("CAR-1")
        self.assertEqual(place, 0)
        self.assertEqual(parking.available_place_numbers(), (1,))
        parking.leave(place)
        self.assertEqual(parking.available_place_numbers(), (0, 1))

    def test_counter_interface(self) -> None:
        c = Counter()
        c.add("a")
        c.add("a")
        c.add("b")
        self.assertEqual(c.count("a"), 2)
        self.assertEqual(c.count("missing"), 0)

    def test_laundry_schedules_by_day_and_hour(self) -> None:
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        sender = RecordingSender()
        laundry = Laundry(LaundrySchedule(), LaundryPricing(),
                          LaundryRepository(connection), sender)
        student = Student("Rustam", "id", True)
        first = laundry.book(student, 3, 10, "wash", "2026-10-21")
        self.assertEqual(first.price, Decimal("7200.00"))
        with self.assertRaises(ValueError):
            laundry.book(student, 3, 10, "wash", "2026-10-21")
        other_hour = laundry.book(student, 3, 18, "wash+dry", "2026-10-21")
        self.assertEqual(other_hour.price, Decimal("12600.00"))
        self.assertEqual(len(sender.messages), 2)

    def test_library_persists_and_handles_commas(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "library.sqlite"
            with sqlite3.connect(db_path) as conn:
                ledger = FineLedger(conn)
                lib = Library(FineCalculator(), ledger, FineNotifier(NoopSender()))
                fine = lib.return_book(Reader("Reader", "r@example.test", "gold"),
                                       Book("Algorithms, Part 1", Decimal("800")), 4)
                self.assertEqual(fine, Decimal("800"))
                self.assertEqual(month_total_csv(ledger.export_csv()), Decimal("800"))
            with sqlite3.connect(db_path) as conn:
                reloaded = FineLedger(conn)
                self.assertEqual(reloaded.total(), Decimal("800"))

    def test_coupling_and_other_rules(self) -> None:
        self.assertEqual(discount_for_level("gold"), Decimal("0.10"))
        self.assertEqual(is_leap_year(2024), True)
        self.assertEqual(is_leap_year(2100), False)
        self.assertEqual(is_adult(17), False)
        self.assertEqual(max_of_three(2, 9, 5), 9)
        self.assertEqual(CurrencyPolicy("USD").format_amount(Decimal("1.236")), "1.24 USD")
        self.assertEqual(PhoneNumbers().to_gateway_digits("+998901234567"), "998901234567")
        self.assertEqual(CheckInRules(StudentStore({1: Decimal(0)})).check_in(1, "C"),
                         CheckInResult("OK", "C"))


if __name__ == "__main__":
    main()


# ============================================================================
# WRITTEN ANSWERS FOR EVERY QUESTION (1–39)
# These are comments because the attached laboratory is a design-on-paper lab.
# The working examples above implement the main requested redesigns.
# ============================================================================

# ============================================================================
# Quick reference
# ============================================================================
# Cohesion (worst → best): coincidental, logical, temporal, procedural, communicational, sequential,
# functional.
# Coupling (worst → best): content, common, external, control, stamp, data.

# ============================================================================
# Part A — Modularity and information hiding
# ============================================================================

# ============================================================================
# 1. One job, one sentence
# ============================================================================
# (a)  Two modules. Timetable stores lessons for each group. SMSReminder sends lesson reminders to
# students.
# (b)  One module. Grades computes a student’s final mark.
# (c)  Two modules. Auth verifies login credentials. LoginScreen displays the login interface.
# (d)  One module. PDFExport converts a finished report into a PDF document.

# ============================================================================
# 2. Cut a cinema system into modules
# ============================================================================
# 1. Modules  SessionCatalog manages film sessions. SeatRegistry tracks available seats per session.
# TicketSales sells tickets. TicketPrinter produces tickets with QR codes. SalesReport counts sales
# per film.
# 2. Dependency arrows  The module calling another is written on the left of the arrow:
# TicketSales ──> SessionCatalog
# TicketSales ──> SeatRegistry
# TicketSales ──> TicketPrinter
# SalesReport ──> TicketSales
# SalesReport ──> SessionCatalog
# 3. Count  Five arrows. SessionCatalog has the most incoming arrows (two). This is not
# automatically a problem: it is a problem only if its public interface is unstable or exposes
# internals.

# ============================================================================
# 3. Where is the module border wrong?
# ============================================================================
# (a)  Modules were divided by syntax, not responsibility. Group code by features or cohesive jobs,
# such as Booking or Validation, rather than all loops versus all conditions.
# (b)  Account balance has no single owner. Account should own the balance and expose operations
# such as add_credit(amount) or deduct(amount); Booking, Refund and Admin must not mutate the field
# directly.
# (c)  The external dependency crosses multiple module borders. Put Telegram API details in one
# TelegramGateway / Notifier module used by Booking, Report and Admin.
# (d)  Things that repeatedly change together were separated. Put the related discount and tax
# policy in a cohesive PricingPolicy component with one change boundary.

# ============================================================================
# 4. A parking lot with no secrets
# ============================================================================
# 1. Coupling  All three outside statements depend on Parking’s internal representation: content
# coupling, because callers directly read or write its data.
# 2. After switching to an occupied-place dictionary  The assignment places[12] = car_number still
# inserts a mapping, but can overwrite a car without validation. “None in parking.places” checks
# dictionary keys, so it is false even when parking is mostly empty: a silent and dangerous
# availability error. The calculation using parking.prices still works if that dictionary is
# unchanged, but remains fragile.
# 3. Public interface  Four signatures, with no exposure of the list, dictionary or prices:
# Parking.park(car_number, vehicle_type)
# Parking.leave(place_number)
# Parking.has_free_place()
# Parking.calculate_cost(vehicle_type, hours)
# 4. Secrets  How occupied places are represented (list or dictionary); how prices and billing rules
# are stored or calculated.

# ============================================================================
# 5. “Just give me the list”
# ============================================================================
# Do not return the internal list, because the screen could modify it and would become dependent on
# its representation. Add available_place_numbers() that returns a new, read-only snapshot of free
# place numbers.

# ============================================================================
# Part B — Abstraction
# ============================================================================

# ============================================================================
# 6. Three words students confuse
# ============================================================================
# Answers  (a) Encapsulation; (b) Information hiding; (c) Abstraction; (d) Information hiding; (e)
# Abstraction.
# Why: (a) bundles state and related operations; (b) hides a private attribute behind a public
# method; (c) exposes what an operation does, not how; (d) deliberately conceals a formula; (e)
# offers a common interface despite different internals.

# ============================================================================
# 7. Procedural or data abstraction?
# ============================================================================
# Classification  (a) D; (b) P; (c) P; (d) D; (e) P; (f) D.
# Example P  For backup_database(), the caller does not need to know the database engine, file
# location or backup commands.
# Example D  For queue.enqueue(x) and queue.dequeue(), the caller does not need to know whether the
# queue uses an array or linked nodes.

# ============================================================================
# 8. Put the abstraction levels in order
# ============================================================================
# Order  C → D → F → A → E → B (user tap → chat API → message object → HTTP → socket → radio
# hardware).
# Level | Knows | Does not need to know
# C: user taps Send | Which text to send | Chat implementation or network protocol
# D: chat.send(chat_id, text) | Conversation identifier, text | Message storage and wire bytes
# F: Message.create(...) | Sender and text fields | HTTP requests or Wi-Fi
# A: http.post(...) | Endpoint and JSON body | TCP packet details
# E: socket.send(data_bytes) | Byte payload / socket | Radio transmission details
# B: Wi-Fi chip | How to transmit radio signals | Meaning of the chat message
#

# ============================================================================
# 9. One interface, two implementations
# ============================================================================
# 1. Client changes  None, as long as the client only calls Counter.add(word) and
# Counter.count(word). The implementation is hidden.
# 2. Speed  Version 2 is faster for 1,000 count calls after one million additions: dictionary lookup
# is about O(1) on average; version 1 must scan the list, O(n) per count call. Both perform
# approximately O(1) work for each addition.
# 3. Promise  The interface promises a correct count, not a particular algorithm or speed. You can
# replace its internals without changing callers, although performance still matters when choosing
# the implementation.

# ============================================================================
# 10. How much should the interface show?
# ============================================================================
# 1. Labels  (a) Too much; (b) Too little; (c) Just enough.
# 2. Broken rule  DRY. Screens will duplicate the timer’s remaining-time calculation; after a timer
# rule changes, screens may show a different value from the actual exam timer.
# 3. Safe internal rewrites  Change the internal time representation from a decreasing counter to a
# deadline timestamp; replace the clock/timer implementation or expiry algorithm. The four public
# methods remain the same.

# ============================================================================
# Part C — Cohesion
# ============================================================================

# ============================================================================
# 11. Name the cohesion
# ============================================================================
# Piece | Cohesion | Why
# (a) make_thumbnail | Sequential | Each processing step consumes the preceding result.
# (b) end_of_day | Temporal | Unrelated actions are grouped because they occur at closing time.
# (c) is_leap_year | Functional | It performs only one computation.
# (d) Misc | Coincidental | Three unrelated utilities merely share a class.
# (e) passport_summary | Communicational | Several operations work on the same passport data.
# (f) export(report, fmt) | Logical | A format flag chooses one of several similar operations.
# (g) register_for_exam | Procedural | Actions follow a required workflow order.
#

# ============================================================================
# 12. Three versions, three levels
# ============================================================================
# 1. Classification  A = sequential; B = communicational; C = procedural.
# 2. Diagnostic question  “Do successive lines consume one another’s results (sequential), just
# share the same input data (communicational), or mainly have to happen in a fixed order
# (procedural)?”
# 3. Temporal versus procedural  Temporal means actions are grouped because they happen at the same
# time or event; procedural means the ordering itself is essential. Version C is procedural: the
# printer must open before printing and close afterward.

# ============================================================================
# 13. The “and” test on a real class
# ============================================================================
# 1. Description  “Invoice adds items and calculates totals and produces PDFs and emails customers
# and saves records.” The sentence contains four “and” connectors, revealing mixed responsibilities.
# 2. Methods changed  (a) email_to_customer; (b) total; (c) save_to_db; (d) to_pdf. This is at least
# four separate reasons to change the class.
# 3. Single-job redesign  Class names and method names only:
# Invoice: add_line(product, qty), total()
# InvoicePdfExporter: export(invoice)
# InvoiceMailer: send(invoice, address)
# InvoiceRepository: save(invoice)

# ============================================================================
# 14. Read the signals
# ============================================================================
# Five signals  (1) Generic name “DataProcessor”; (2) extreme size, 1,400 lines; (3) rapid growth,
# roughly 100 lines weekly; (4) unrelated dependencies (sqlite3, smtplib, reportlab, requests) and
# disjoint fields self.connection versus self.smtp; (5) unrelated change reasons (PDF layout, SMS
# provider and SQL query).
# Strongest evidence  Three independent reasons to change show divergent responsibilities. In 30
# seconds, inspect the file’s recent commit history (for example, git log --oneline --
# DataProcessor.py) and compare commit descriptions; no full code reading is necessary.

# ============================================================================
# 15. When is temporal cohesion acceptable?
# ============================================================================
# 1. Acceptable case  A short, high-level coordinator may invoke cohesive modules at one event or
# time. This fits modularity: the coordinator handles the order, while each module owns its own
# work.
# 2. Two new problems  (i) The function now mixes business calculations, SQL storage, e-mail
# transport and light control, so it has many reasons to change. (ii) It depends on concrete
# sqlite3, SMTP and hardware details, making testing, replacement and error handling difficult.

# ============================================================================
# Part D — Coupling
# ============================================================================

# ============================================================================
# 16. Name and order the coupling
# ============================================================================
# Case | Type | Reason
# (a) | Stamp | The whole 15-field User is passed although only phone is used.
# (b) | External | Two modules rely on one external semicolon-separated file format.
# (c) | Data | Only the two necessary numeric values are passed.
# (d) | Content | Report reaches into Database._connection.
# (e) | Common | Two functions share mutable global CURRENT_USER.
# (f) | Control | The style flag chooses a branch inside the function.
#
# Worst → best  (d) → (e) → (b) → (f) → (a) → (c).

# ============================================================================
# 17. Move one step down the coupling table
# ============================================================================
# 1. Replace stamp with data  Only pass the phone number:
# send_sms(phone)
# send_sms(user.phone)
# 2. Remove control flag  Choose the intended operation by its name:
# format_price_short(amount)
# format_price_long(amount)
# 3. Remove common/global state  A Session object owns the current user:
# Session.login(name)
# Session.can_delete()  # checks this Session instance
# 4. Remove content coupling  Database exposes a safe query instead of its private connection:
# Database.fetch_sales()
# Report.build(db)  # obtains rows via db.fetch_sales()

# ============================================================================
# 18. The same boolean, two kinds of coupling
# ============================================================================
# 1. Difference  create_user(name, is_admin) uses is_admin as actual user data, so it is data
# coupling. save(user, to_cloud) uses a boolean to select an internal algorithm, so it is control
# coupling.
# 2. Repair  save(user, True) does not reveal that True means cloud. Replace it with
# save_to_cloud(user) or save_to_disk(user) (or distinct writer objects).

# ============================================================================
# 19. Who decides the messenger?
# ============================================================================
# 1. Three decisions  AttendanceReport chooses the Telegram service, hardcodes its token and
# hardcodes the destination group. These belong to configuration / messaging infrastructure.
# 2. Requested changes  To use e-mail you must edit AttendanceReport to replace Telegram code. To
# send nothing in tests you must edit it again or monkeypatch Telegram — both show excessive
# coupling.
# 3. Inject the sender  Keep the class focused on the report; pass in a service with send(text):
# AttendanceReport(sender): send(text) -> sender.send(text)
# real = AttendanceReport(TelegramSender(token, group))
# test = AttendanceReport(NullSender())

# ============================================================================
# 20. Place it on the golden-rule square
# ============================================================================
# Design | Cohesion | Coupling | Corner
# (a) huge shared System | Low | High | Worst: low / high
# (b) single-job classes sharing SETTINGS | High | High | High / high
# (c) unrelated independent utils files | Low | Low | Low / low
# (d) injected Pricing, Storage, Receipt | High | Low | Goal: high / low
#
# Improve (b)  Replace the mutable global dictionary with an injected, controlled settings/policy
# interface; each class receives only the settings service or values it needs.

# ============================================================================
# Part E — Separation of concerns, DRY, KISS, YAGNI
# ============================================================================

# ============================================================================
# 21. Which rule is broken?
# ============================================================================
# Case | Broken principle | One-line repair
# (a) | DRY | Define MAX_STUDENTS once and use it for enrolment checks and messages (use >= at the
# limit).
# (b) | KISS | return age >= 18
# (c) | YAGNI | Keep the single teacher role; introduce permissions only when required.
# (d) | Separation of concerns | Make the button handler call business and storage services, then
# display their result.
# (e) | KISS | return max(a, b, c)
#

# ============================================================================
# 22. Same code, different knowledge
# ============================================================================
# Do not merge the functions: delivery weight and parking hours are independent business rules that
# happen to use the same number today. Keep SHIP_RATE_PER_KG = 2000 in shipping policy and
# PARKING_RATE_PER_HOUR = 2000 in parking policy, each defined once, because one rate may change
# without the other.

# ============================================================================
# 23. YAGNI or simple good design?
# ============================================================================
# Developer A is doing good design: messages.py centralizes existing texts at low cost, so
# maintenance becomes easier. Developer B breaks YAGNI: seven languages, a picker and a download
# system have immediate development/test costs, yet the customer requested only Uzbek and no such
# benefit is needed now.

# ============================================================================
# 24. Sort the lines by concern
# ============================================================================
# Concern | Line numbers | Reason
# Presentation | 3, 7 | Displays a message / changes a button color.
# Business rules | 1, 5 | Checks balance / calculates discount eligibility.
# Storage | 2, 8 | Inserts and queries database rows.
# Infrastructure | 4, 6 | Logging and SMS integration.
#
# OrderScreen  It should own presentation only and ask other components to perform business rules,
# persistence or infrastructure work.

# ============================================================================
# Part F — Case study: dormitory laundry
# ============================================================================

# ============================================================================
# 25. Count the jobs
# ============================================================================
# 1. Six jobs  (1) Check whether a machine is free; (2) mark the machine as reserved; (3) calculate
# mode price and resident discount; (4) save the booking in a text file; (5) send a Telegram
# confirmation; (6) print user feedback.
# 2. Cohesion  Mainly procedural cohesion: these different responsibilities are held together by the
# order of the booking workflow, not by one small job. This is too much responsibility for one
# method.
# 3. Numeric literals  Four occurrences: 8000, 8000, 6000 and 0.10. There are three distinct values;
# 8000 appears twice. The “:00” in a string is not a numeric literal.

# ============================================================================
# 26. Name every coupling
# ============================================================================
# (a)  Global STATUS: common coupling.
# (b)  mode: control coupling, because “wash” versus “wash+dry” selects an internal branch.
# (c)  bookings.txt with semicolons: external coupling to a shared file protocol.
# (d)  Whole student object: stamp coupling, because only three fields are used.
# (e)  Direct telegram.send(...): a hard-coded dependency on external messaging infrastructure;
# tightly couples business workflow to the Telegram API.

# ============================================================================
# 27. Who owns STATUS?
# ============================================================================
# 1. Behaviour  Rustam reserves machine 3 at 10:00, setting STATUS[3] = “busy”. Malika is rejected
# at 18:00 even though it is another slot. Without a reset, the same machine still appears busy
# tomorrow.
# 2. Owner  BookingRepository (or MachineSchedule) alone owns reservations indexed by both machine
# and date/time. Its public operations can be:
# BookingRepository.is_available(machine, date, hour)
# BookingRepository.reserve(student_id, machine, date, hour)
# BookingRepository.cancel(machine, date, hour)
# BookingRepository.get_bookings(start_date, end_date)
# 3. Writers  No other module directly writes the reservation representation. Other modules call the
# repository’s methods only.

# ============================================================================
# 28. Redesign on paper
# ============================================================================
# 1. Class interfaces  One coordinator receives dependencies in its constructor:
# LaundryBooking(repository, pricing, notifier): book(student, machine, date, hour, mode)
# BookingRepository: is_available(machine, date, hour), reserve(student_id, machine, date, hour,
# price), get_bookings(start, end)
# PriceCalculator: price(mode, is_resident)
# Notifier: send(recipient, text)
# WeeklyReport(repository): machine_hours(start, end)
# 2. Diagram and arrows  Four arrows in total, counting each distinct dependency once:
# LaundryBooking ──> BookingRepository <── WeeklyReport
# |
# +────────> PriceCalculator
# |
# +────────> Notifier
# 3. Constants  8000 (washing rate), 6000 (drying surcharge) and 0.10 (resident discount) are each
# declared once inside PriceCalculator or an injected price policy.
# 4. Output  The presentation layer (screen / CLI) prints “Booked! Price: ...” using the result from
# LaundryBooking; the coordinator does not print it.

# ============================================================================
# 29. The two numbers: four requested changes
# ============================================================================
# Change | Old design: edit | Redesign: change
# (a) Discount 15% | Laundry.book() | PriceCalculator only.
# (b) SMS instead of Telegram | Laundry.book() | Provide an SMS Notifier implementation; do not edit
# LaundryBooking.
# (c) SQLite instead of text | Laundry.book() and WeeklyReport parser | Replace BookingRepository
# implementation; WeeklyReport keeps the repository interface.
# (d) No side effects in tests | Monkeypatch Laundry.book(), STATUS, file and Telegram dependencies
# | Inject an in-memory repository and a NullNotifier; no production-class edit.
#
# Explanation  “One class changes” in the old design is bad news because that same large class
# changes for unrelated reasons, so it has weak cohesion and a high risk of regressions.

# ============================================================================
# Part G — Coupling in depth
# ============================================================================

# ============================================================================
# 30. The settings everybody reads
# ============================================================================
# 1. Coupling and hidden dependencies  cart.py, invoice.py and admin.py are connected to settings.py
# through common coupling (the same mutable global SETTINGS). cart–invoice, cart–admin and
# invoice–admin also influence one another indirectly, despite not importing each other.
# 2. Two errors + inconsistent state  A cart total calculated in UZS may suddenly display as USD
# without conversion; the display precision also changes from 0 to 2 decimals mid-session. The two
# separate assignments in switch_to_usd() permit an intermediate state of currency = “USD” with
# decimals = 0.
# 3. Changes for rounding step  settings.py (representation), cart.py (rounding logic), invoice.py
# (display formatting) and admin.py (currency switch) would need edits: four files. A correctly
# encapsulated CurrencyPolicy would need one policy-module change (its callers keep the interface).
# 4. Policy API  For example:
# CurrencyPolicy.round_amount(amount)
# CurrencyPolicy.format_amount(amount)
# CurrencyPolicy.get_currency()
# CurrencyPolicy.set_currency(currency)
# Cart knows only how to ask for a rounded amount; Invoice knows only how to ask for a formatted
# amount. Neither knows global fields or precision rules. Only the authorized currency
# administration service can call set_currency(), which updates the policy atomically. Actual
# exchange conversion must also be addressed before changing monetary units.

# ============================================================================
# 31. Data that only travels
# ============================================================================
# 1. Coupling  checkout(order) → confirm(order): stamp; confirm(order) → schedule(order): stamp;
# schedule(order) → delivery_date(city, weight_kg): data. The first two functions merely pass the
# Order onward.
# 2. Address change  With the original signatures, schedule() alone needs source changes to access
# order.addresses instead of order.address; checkout() and confirm() can keep forwarding the object.
# Address selection should be encapsulated by the scheduling boundary, not spread through each
# forwarding function.
# 3. Smaller-parameter flow  Remove the pass-through of the entire Order and pass only delivery
# information at the boundary:
# checkout(city, weight_kg): return confirm(schedule(city, weight_kg))
# confirm(estimated_date): return estimated_date
# schedule(city, weight_kg): return delivery_date(city, weight_kg)
# delivery_date(city, weight_kg): ...
# Parameter counts are 2, 1, 2 and 2. A single boundary adapter should select the city from an
# Order; otherwise every caller would learn the Order address layout. If you require schedule()
# itself to own address selection, let only schedule(order) accept an Order and call it directly
# from checkout; that is a justified, localized stamp-coupling trade-off.
# 4. Six fields  Prefer one focused Order / ConfirmationDetails record rather than six positional
# arguments when those fields form a coherent concept. Six data parameters give low coupling but a
# long, easily misordered signature; passing Order is shorter but ties confirm() to the whole object
# and its future changes. A small purpose-built record balances both costs.

# ============================================================================
# 32. Fewer arrows, more surprises
# ============================================================================
# 1. Number of known collaborators  Version 1 directly knows three service modules (fines, notifier,
# stats). Version 2 knows only a listener/callback interface, not each registered concrete listener.
# 2. Remaining coupling  Stamp coupling: each listener receives the entire loan object. If a field
# all three use disappears, all three may break even though Loans does not directly name them.
# 3. Order and risk  Version 1 visibly runs fines → notifier → stats. In version 2, order comes from
# subscribe() call order in the registration/bootstrap code; a notification can be sent before fines
# are recorded, or one failing callback can prevent the others from executing.
# 4. Choice  Keep version 1 for two stable listeners: simpler, explicit ordering. Prefer version 2
# for twelve listeners owned by five teams: new subscribers can be added without repeatedly editing
# Loans, with documented event contracts and failure/order rules.

# ============================================================================
# 33. The loop of imports
# ============================================================================
# 1. Import cycle  orders.py → inventory.py → pricing.py → orders.py. In the unmodified code,
# importing any one normally pulls in all three, making isolated imports/tests fragile or impossible
# without stubs.
# 2. Portable package  pricing.py cannot travel alone: it imports Order from orders.py, which in
# turn imports inventory.py (and thus pricing.py again). These dependencies must travel or the
# import must be removed.
# 3a. Break loop by moving a function  Move discount(order) to orders.py (short-term trade-off).
# pricing.py then has stock_value(items) only. Arrows:
# orders.py ──> inventory.py ──> pricing.py
# 3b. Break loop by passing narrower data  Keep discount in pricing.py, but change its signature to
# discount(customer_level). Remove “from orders import Order”; the chain of arrows is again:
# orders.py ──> inventory.py ──> pricing.py
# 4. Dependency order  Least to most knowledge: pricing.py, inventory.py, orders.py. This acyclic
# order supports predictable imports/builds and testing lower-level modules independently.

# ============================================================================
# Part H — DRY, KISS, YAGNI in depth
# ============================================================================

# ============================================================================
# 34. One rule, five places
# ============================================================================
# 1. Repeated knowledge  registration.py knows “+998 plus 9 digits”; sms.py assumes 13 characters
# and strips “+”; receipt.py assumes the fixed prefix/mask layout; schema.sql assumes +998 and
# length 13; test_data.py hardcodes samples with the same country format. The rule is repeated as
# knowledge, not necessarily identical source lines.
# 2. Kazakhstan migration  Potentially all five places need review/change. The receipt mask is easy
# to forget because it looks only cosmetic; it may expose the wrong digits or produce an
# inappropriate grouping after the number length changes.
# 3. Owner and interface  Introduce PhoneNumberPolicy:
# PhoneNumberPolicy.is_valid(phone)
# PhoneNumberPolicy.normalize(phone)
# PhoneNumberPolicy.to_gateway_digits(phone)
# PhoneNumberPolicy.mask(phone)
# Registration, SMS, receipt code and tests can call or derive cases from this module. A SQL CHECK
# constraint in schema.sql cannot call an ordinary Python module directly.
# 4. Deliberate duplication  Keeping a database validation CHECK as a defense at the storage
# boundary is justified even if Python validates first. Add integration/contract tests (or generate
# the SQL constraint from a shared specification) so the two protections cannot silently drift
# apart.

# ============================================================================
# 35. DRY gone too far
# ============================================================================
# 1. Coupling, cohesion and variants  kind and the three boolean switches create control coupling;
# calculate() has logical cohesion around alternative behaviours and also mixes calculation with
# notification. There are 3 × 2 × 2 × 2 = 24 theoretical requested behaviours, but only three are
# used.
# 2. Principles  The developer pursued DRY, but violated KISS (many branching options) and YAGNI (21
# unused combinations). Sending SMS inside the calculation also violates separation of concerns.
# 3. Redesign  Keep one shared subtotal operation; give invoice, refund and quote a clear operation
# each. Put notification in a separate caller/service:
# subtotal(items) = sum(item.price * item.qty for item in items)
# invoice_total(items) = ceil((subtotal(items) * 1.12) / 100) * 100
# refund_total(items) = -(subtotal(items) * 1.12)
# quote_total(items) = subtotal(items)
# # Caller sends SMS separately when required.
# No control flags remain. The shown calculations preserve the three currently used combinations;
# rounding and tax rules should ultimately be constants owned by a pricing policy.
# 4(a)  Two functions validating the same 13-character phone format repeat one business rule. Share
# one validation function / policy (DRY).
# 4(b)  Similar loops summing prices and weights encode different knowledge; do not force them into
# one highly configurable function simply because the loops look alike.

# ============================================================================
# 36. When two principles disagree
# ============================================================================
# (a) VAT  DRY versus loose coupling/independent deployment. Prefer keeping a versioned,
# independently releasable policy in each service, with matching contract tests; share one library
# when both services actually deploy together or coordinated changes are cheaper than duplication.
# (b) Monthly script  Separation of concerns versus KISS/YAGNI. Keep the short readable script;
# reconsider classes if it grows, gains several callers, or genuinely develops independently
# changing responsibilities.
# (c) Cache  Information hiding versus performance. Keep the internal entries secret: optimize get()
# or expose get_many(keys) / a read-only iterator to avoid one million expensive calls. Reconsider
# revealing a stable read-only view only if measurement proves a narrow public batch API still
# cannot meet an essential performance requirement.

# ============================================================================
# 37. The arrows point the wrong way
# ============================================================================
# 1. Current arrows  storage.py → screens.py (wrong), rules.py → storage.py, screens.py → rules.py.
# storage.py improperly imports presentation for error_text; rules.py improperly returns HTML
# presentation markup.
# 2. Telegram bot impact  The storage error text is locked to Uzbek and the rules return
# HTML/English. You would need to change storage.py and rules.py to return language-neutral results
# and add a Russian bot presenter; otherwise the bot must copy and strip/translate presentation
# formatting and possibly duplicate business logic.
# 3. Layered redesign  storage.find_student(id) returns data or raises a typed StudentNotFound error
# (no sentence). rules.check_in(id, room) returns a structured result such as status=BLOCKED_DEBT or
# status=OK with room (no HTML/text). screens.check_in_page(form) renders a localized UI from that
# status. The Telegram bot renders Russian text separately in its own presentation module.
# 4. New arrows  screens.py → rules.py → storage.py: two import arrows across the three original
# modules. Presentation is allowed to know both rules and storage if necessary, though it should
# normally use only rules. Storage should know neither business rules nor presentation.

# ============================================================================
# Part I — Case study: library fines
# ============================================================================

# ============================================================================
# 38. Audit the code
# ============================================================================
# 1. Five supported design problems  The following code fragments provide evidence for five of the
# seven areas:
# Area | Evidence and why
# Information hiding | FINES = [] is a public mutable global whose representation callers may rely
# on.
# Cohesion | Library.return_book both calculates fines and writes CSV and sends e-mail and prints
# output.
# Coupling | MonthlyReport depends on fines.csv positional fields; Library calls email.send
# directly.
# Separation of concerns | with open("fines.csv", "a") and print("Fine:", fine) appear in a business
# workflow.
# DRY | The same fine is stored in FINES and fines.csv; total_fines and month_total depend on
# separate copies.
#
# No clear evidence proves a KISS violation or a YAGNI violation: the code is not visibly
# overcomplicated, and no unrequested future feature is shown. Do not invent either problem.
# 2. Comma in a title  For “Algorithms, Part 1”, the CSV line has an extra comma. line.split(",")
# produces four pieces, so unpacking exactly three variables raises ValueError. This is external
# coupling to an inadequate CSV contract. Neither Library nor MonthlyReport is solely at fault: the
# storage contract has no proper shared ownership/escaping.
# 3. Restart mismatch  FINES is an in-memory list, so it becomes empty on restart; fines.csv
# persists. total_fines() can return zero while month_total() sees historical fines. The root cause
# is duplicated state/sources of truth (DRY), reinforced by weak data ownership.
# 4. Three safe, ordered improvements  (1) First make MonthlyReport total the last numeric field
# safely even when a legacy title contains a comma; this immediately fixes the demonstrated crash
# without changing stored data. (2) Make total_fines() read the same persistent ledger instead of
# FINES, so restarting cannot lose one view. (3) Encapsulate the ledger, remove FINES, and use the
# csv library to write valid escaped CSV and to parse records; account for existing legacy rows
# during migration. The first fix comes first because otherwise an existing “Algorithms, Part 1”
# entry prevents reliable reporting.

# ============================================================================
# 39. Two designs, five changes
# ============================================================================
# 1. Change table  “Edit” refers to modifying an existing class; “add” means a new implementation
# and its wiring. Interface implementations may also require updates to dependency configuration.
# Requested change | Design X (4 classes) | Design Y (11 classes)
# (a) Gold pays 70% instead of 50% | Edit FineCalculator. | Edit GoldDiscountRule.
# (b) Silver pays 80% | Edit FineCalculator. | Add SilverDiscountRule; edit RuleChain
# setup/registration.
# (c) Use SQLite | Edit FineLedger; keep its API. | Add SqliteFineRepository; update
# composition/wiring to select it.
# (d) First 3 days free | Edit FineCalculator. | Edit DaysLateRule (or add a GracePeriodRule plus
# registration).
# (e) E-mail plus SMS | Edit Notifier. | Add SmsChannel and CompositeNotificationChannel; update
# channel wiring.
#
# 2. Design X arrows  Library → FineCalculator, Library → FineLedger, Library → Notifier,
# MonthlyReport → FineLedger = 4 dependency arrows. FineLedger owns persisted fine format.
# Library ──> FineCalculator
# |──────> FineLedger <── MonthlyReport
# +──────> Notifier
# Design Y arrows  Count class-to-class dependencies and interface implementations explicitly:
# Library ──> FineService
# FineService ──> RuleChain, FineRepository, NotificationChannel
# RuleChain ──> FineRule
# DaysLateRule, GoldDiscountRule, PriceCapRule ──> FineRule
# CsvFineRepository ──> FineRepository
# EmailChannel ──> NotificationChannel
# MonthlyReport ──> FineRepository
# This representation has 11 arrows: seven usage/dependency arrows plus four rule/repository/channel
# interface implementation arrows. CsvFineRepository owns the CSV layout; a new SQLite repository
# would own its own table format. Exact arrow totals depend on whether UML interface-implementation
# links are counted; both designs must use the same counting convention.
# 3. Hand-in recommendation  Choose Design X for the stated small library: one calculator, one
# ledger and one notifier cover the five concrete requests with far less complexity. Design Y risks
# YAGNI because the customer asks only for specific rule, storage and notification changes, not a
# general plug-in framework. Move toward Y if independent teams frequently introduce many new fine
# rules or storage/notification implementations that must be swapped without changing existing
# components.
