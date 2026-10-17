
import os
import logging
import database

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

STATION, AREA, FUEL, AVAILABILITY, NOTES = range(5)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "أهلاً بك في دليل المحروقات | حمص ⛽\n\n"
        "يساعدك البوت على متابعة بلاغات توفر البنزين والمازوت.\n\n"
        "/stations - عرض البلاغات الحديثة\n"
        "/areas - إحصائيات البلاغات حسب المنطقة\n"
        "/nearby - معلومات عن خدمة المحطات القريبة\n"
        "/report - إرسال بلاغ جديد\n"
        "/help - المساعدة"
    )


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.effective_message.reply_text(
        "📝 لنبدأ بإرسال البلاغ.\n\n"
        "ما اسم محطة الوقود؟\n"
        "أرسل اسم المحطة أو اكتب: غير معروف\n\n"
        "للإلغاء أرسل /cancel"
    )
    return STATION


async def receive_station(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    context.user_data["station_name"] = (
        update.effective_message.text.strip()
    )
    await update.effective_message.reply_text(
        "📍 في أي منطقة تقع المحطة؟"
    )
    return AREA


async def receive_area(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    context.user_data["area"] = update.effective_message.text.strip()

    await update.effective_message.reply_text(
        "⛽ ما نوع المحروقات؟",
        reply_markup=ReplyKeyboardMarkup(
            [["بنزين", "مازوت"]],
            one_time_keyboard=True,
            resize_keyboard=True,
        ),
    )
    return FUEL


async def receive_fuel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    fuel = update.effective_message.text.strip()

    if fuel not in ("بنزين", "مازوت"):
        await update.effective_message.reply_text(
            "يرجى اختيار بنزين أو مازوت من الأزرار."
        )
        return FUEL

    context.user_data["fuel_type"] = fuel

    await update.effective_message.reply_text(
        "📊 ما حالة المحروقات؟",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["متوفر", "غير متوفر"],
                ["طابور طويل", "لا أعرف"],
            ],
            one_time_keyboard=True,
            resize_keyboard=True,
        ),
    )
    return AVAILABILITY


async def receive_availability(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    availability = update.effective_message.text.strip()
    allowed = ("متوفر", "غير متوفر", "طابور طويل", "لا أعرف")

    if availability not in allowed:
        await update.effective_message.reply_text(
            "يرجى اختيار إحدى الحالات من الأزرار."
        )
        return AVAILABILITY

    context.user_data["availability"] = availability

    await update.effective_message.reply_text(
        "📝 أرسل ملاحظات إضافية إن وجدت.\n"
        "مثال: يوجد طابور طويل.\n\n"
        "أو اضغط «لا توجد ملاحظات».",
        reply_markup=ReplyKeyboardMarkup(
            [["لا توجد ملاحظات"]],
            one_time_keyboard=True,
            resize_keyboard=True,
        ),
    )
    return NOTES


async def receive_notes(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    notes = update.effective_message.text.strip()

    if notes == "لا توجد ملاحظات":
        notes = ""

    data = context.user_data

    try:
        duplicate = database.is_duplicate_report(
            station_name=data["station_name"],
            area=data["area"],
            fuel_type=data["fuel_type"],
            availability=data["availability"],
            minutes=30,
        )

        if duplicate:
            await update.effective_message.reply_text(
                "⚠️ هذا البلاغ مسجل مسبقًا خلال آخر 30 دقيقة.\n"
                "لم تتم إضافة نسخة مكررة."
            )
            context.user_data.clear()
            return ConversationHandler.END

        report_id = database.add_report(
            station_name=data["station_name"],
            area=data["area"],
            fuel_type=data["fuel_type"],
            availability=data["availability"],
            notes=notes,
        )

        logging.info("تم حفظ البلاغ رقم %s", report_id)

    except Exception:
        logging.exception("تعذر حفظ البلاغ أو فحص التكرار")
        await update.effective_message.reply_text(
            "❌ تعذر حفظ البلاغ بسبب خطأ داخلي.\n"
            "يرجى المحاولة لاحقًا."
        )
        context.user_data.clear()
        return ConversationHandler.END

    await update.effective_message.reply_text(
        f"✅ تم حفظ البلاغ بنجاح!\n"
        f"رقم البلاغ: {report_id}\n\n"
        "يمكنك استخدام /stations لعرض البلاغات الحديثة، "
        "أو /areas لعرض الإحصائيات حسب المنطقة.",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["/stations", "/areas"],
                ["/nearby", "/report"],
            ],
            resize_keyboard=True,
        ),
    )

    context.user_data.clear()
    return ConversationHandler.END


async def stations(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    try:
        reports = database.get_recent_reports(hours=6, limit=10)
    except Exception:
        logging.exception("تعذر جلب البلاغات")
        await update.effective_message.reply_text(
            "تعذر عرض البلاغات حاليًا. يرجى المحاولة لاحقًا."
        )
        return

    if not reports:
        await update.effective_message.reply_text(
            "لا توجد بلاغات حديثة خلال آخر 6 ساعات.\n"
            "يمكنك إرسال بلاغ باستخدام /report."
        )
        return

    messages = [
        "⛽ أحدث بلاغات المحروقات في حمص",
        "🕒 البلاغات خلال آخر 6 ساعات:\n",
    ]

    for item in reports:
        messages.append(
            f"📍 المحطة: {item['station_name']}\n"
            f"🗺 المنطقة: {item['area']}\n"
            f"⛽ النوع: {item['fuel_type']}\n"
            f"📊 الحالة: {item['availability']}\n"
            f"📝 الملاحظات: {item['notes'] or 'لا توجد'}\n"
            f"🕒 الوقت: {item['created_at']}\n"
            "──────────────"
        )

    text = "\n".join(messages)

    for index in range(0, len(text), 3500):
        await update.effective_message.reply_text(
            text[index:index + 3500]
        )


async def areas(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    try:
        area_counts = database.get_area_report_counts(hours=6)
    except Exception:
        logging.exception("تعذر جلب إحصائيات المناطق")
        await update.effective_message.reply_text(
            "تعذر عرض إحصائيات المناطق حاليًا. يرجى المحاولة لاحقًا."
        )
        return

    if not area_counts:
        await update.effective_message.reply_text(
            "📍 لا توجد بلاغات خلال آخر 6 ساعات.\n"
            "يمكنك إرسال بلاغ باستخدام /report."
        )
        return

    total = sum(item["report_count"] for item in area_counts)

    lines = [
        "📍 إحصائيات المحروقات حسب المنطقة",
        "🕒 خلال آخر 6 ساعات:\n",
    ]

    for item in area_counts:
        count = item["report_count"]
        lines.append(f"📍 {item['area']}: {count} بلاغ")

    lines.append(f"\n📊 إجمالي البلاغات: {total}")

    await update.effective_message.reply_text("\n".join(lines))


async def nearby(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    await update.effective_message.reply_text(
        "⛽ المحطات القريبة منك\n\n"
        "أهلاً بك في دليل المحروقات | حمص.\n\n"
        "📍 نعمل على تطوير خدمة تساعدك في معرفة "
        "محطات الوقود القريبة منك وحالة توفر البنزين والمازوت.\n\n"
        "🚧 هذه الخدمة قيد التطوير وستتوفر قريباً.\n\n"
        "ساهم معنا بإرسال بلاغ عن حالة المحروقات عبر /report."
    )


async def cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    context.user_data.clear()

    await update.effective_message.reply_text(
        "تم إلغاء إرسال البلاغ. يمكنك البدء من جديد باستخدام /report."
    )
    return ConversationHandler.END


async def help_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    await update.effective_message.reply_text(
        "دليل المحروقات | حمص ⛽\n\n"
        "/start - تشغيل البوت\n"
        "/stations - عرض البلاغات الحديثة خلال 6 ساعات\n"
        "/areas - إحصائيات البلاغات حسب المنطقة خلال 6 ساعات\n"
        "/nearby - معلومات عن خدمة المحطات القريبة\n"
        "/report - إرسال بلاغ جديد\n"
        "/cancel - إلغاء البلاغ\n"
        "/help - المساعدة\n\n"
        "تعتمد دقة المعلومات على البلاغات التي يرسلها المستخدمون."
    )


async def error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
):
    logging.error(
        "حدث خطأ أثناء معالجة تحديث تيليغرام",
        exc_info=context.error,
    )


def main():
    database.init_db()
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        print("خطأ: لم يتم إعداد TELEGRAM_BOT_TOKEN.")
        print(
            'نفّذ: $env:TELEGRAM_BOT_TOKEN = '
            'Read-Host "أدخل رمز البوت"'
        )
        return

    app = Application.builder().token(token).build()

    report_conversation = ConversationHandler(
        entry_points=[CommandHandler("report", report)],
        states={
            STATION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_station,
                )
            ],
            AREA: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_area,
                )
            ],
            FUEL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_fuel,
                )
            ],
            AVAILABILITY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_availability,
                )
            ],
            NOTES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_notes,
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("report", report),
        ],
        allow_reentry=True,
    )

    app.add_handler(report_conversation)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stations", stations))
    app.add_handler(CommandHandler("areas", areas))
    app.add_handler(CommandHandler("nearby", nearby))
    app.add_handler(CommandHandler("help", help_command))
    app.add_error_handler(error_handler)

    print("دليل المحروقات | حمص يعمل الآن...")
    app.run_polling()


if __name__ == "__main__":
    main()
