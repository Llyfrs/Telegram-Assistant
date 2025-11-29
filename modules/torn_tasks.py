import asyncio
import time
from typing import Any, Dict, List

import telegram
import telegramify_markdown

from modules.database import MongoDB
from modules.torn import Torn, logg_error
from utils.logging import get_logger

logger = get_logger(__name__)


@logg_error
async def send_stock_report(torn: Torn) -> None:
    if torn.company is None:
        await torn.update_company()

    if not torn.company:
        logger.error("Company data is unavailable for stock report")
        return

    company_stock = torn.company.get("company_stock", {})
    detailed = torn.company.get("company_detailed", {})
    upgrades = detailed.get("upgrades", {})

    storage_space = upgrades.get("storage_space")
    if storage_space is None:
        logger.error("Storage space information missing from company data")
        return

    try:
        total_sold = sum(float(v.get("sold_amount", 0)) for v in company_stock.values())
        total_in_stock = sum(float(v.get("in_stock", 0)) + float(v.get("on_order", 0)) for v in company_stock.values())
    except (TypeError, ValueError) as exc:
        logger.error("Failed to aggregate company stock data: %s", exc)
        return

    if total_sold == 0:
        logger.info("No products sold, skipping stock report")
        return

    aim_ratio = storage_space / total_sold
    capacity = storage_space - total_in_stock
    run_out = False

    message = "*Stock Alert*:\n"
    message += f"Capacity to fill: {capacity}\n"
    message += f"Global ratio: {aim_ratio:.2f}\n"

    for key, value in company_stock.items():
        sold = float(value.get("sold_amount", 0))
        if sold <= 0:
            continue

        in_stock = float(value.get("in_stock", 0)) + float(value.get("on_order", 0))
        diff = aim_ratio - (in_stock / sold)

        if diff <= 0.0:
            logger.debug("%s: no purchase required (%.2f)", key, in_stock / sold)
            continue

        buy = diff * sold
        capacity -= buy

        if run_out:
            buy = 0.0
        elif capacity <= 0.0:
            run_out = True
            buy = capacity + buy

        message += f"{key}: {buy:.0f} ({in_stock / sold:.2f})\n"

    message += f"Capacity: {round(capacity, 2)}"

    await torn.send(message)


@logg_error
async def send_train_status(torn: Torn) -> None:
    if torn.company is None:
        await torn.update_company()

    company = torn.company or {}
    detailed = company.get("company_detailed", {})
    trains_available = detailed.get("trains_available", 0)

    if trains_available == 0:
        logger.info("No trains available")
        await torn.send("You have no trains available, you can't train anyone")
        return

    employees = company.get("company_employees", {})
    if not employees:
        logger.info("No employees in company data")
        await torn.send("No employees found to train")
        return

    order: List[str] = MongoDB().get("last_employee_trained", [])

    current_employee_ids = list(employees.keys())
    for employee_id, data in employees.items():
        wage = data.get("wage", 0)
        if wage > 0 and employee_id not in order:
            order.append(employee_id)
        if wage == 0 and employee_id in order:
            order.remove(employee_id)

    order = [employee_id for employee_id in order if employee_id in current_employee_ids]

    if not order:
        order = current_employee_ids.copy()

    if not order:
        await torn.send("No valid employees available for training")
        return

    order.append(order.pop(0))
    MongoDB().set("last_employee_trained", order)

    next_employee = employees[order[0]]
    wage = next_employee.get("wage", 0)
    preference = MongoDB().get("company_employees", {}).get(order[0], None)

    message = (
        f"You have *{trains_available} trains* available and your next employee to train is *{next_employee.get('name')}* "
        f"you can update their wage to `{wage - trains_available}` when you finish. "
        f"[Quick link](https://www.torn.com/companies.php?step=your&type=1)"
    )

    if preference is not None:
        message += f"\n\nPrefers: *{preference}*"

    logger.info(
        "Trains available: %s, next employee: %s", trains_available, next_employee.get('name')
    )

    await torn.send(message)


async def get_valid_bounties(torn: Torn, min_money: int) -> List[Dict[str, Any]]:
    await torn.update_bounties()

    if torn.bounties is None:
        logger.error("Failed to retrieve bounty data")
        return []

    if torn.user is None:
        await torn.update_user()

    if torn.user is None:
        logger.error("User data unavailable, cannot evaluate bounties")
        return []

    monitor: List[Dict[str, Any]] = []
    seen_ids: List[int] = []

    my_bts = torn.user.get("total", 0)
    bounties = torn.bounties.get("bounties", [])

    for bounty in bounties:
        if bounty.get("reward", 0) < min_money:
            continue

        target_id = bounty.get("target_id")
        if target_id in seen_ids:
            continue

        seen_ids.append(target_id)

        bts = await torn.get_bts(target_id)
        if not bts or bts.get("TBS") is None:
            continue

        if my_bts and bts.get("TBS") > my_bts * 1.1:
            continue

        user_info = await torn.get_basic_user(target_id)
        if not user_info:
            continue

        basicicons = user_info.get("basicicons", {})
        if basicicons.get("icon71") is not None or basicicons.get("icon72") is not None:
            continue

        user_info["reward"] = bounty.get("reward")
        user_info["TBS"] = bts.get("TBS")
        user_info["valid_until"] = bounty.get("valid_until")

        monitor.append(user_info)

    return monitor


async def bounty_monitor(torn: Torn) -> None:
    if torn.user is None:
        await torn.update_user()

    if torn.user is None:
        logger.error("Unable to start bounty monitor without user data")
        return

    my_bts = torn.user.get("total", 0)
    chat_message: telegram.Message = await torn.send("Starting Bounty monitor")

    while True:
        monitor = await get_valid_bounties(torn, 500000)

        monitor.sort(key=lambda x: x.get("states", {}).get("hospital_timestamp", 0))

        energy = torn.user.get("energy", {}).get("current", 0)
        message = f"*Bounty Monitor ({energy}e)*\n\n"

        for user in monitor:
            reward = "${:,.0f}".format(user.get("reward", 0))
            tbs = user.get("TBS", 0)
            bts_percentage = 0 if my_bts == 0 else round(tbs / my_bts * 100)

            message += (
                f"[{user.get('name')}](https://www.torn.com/loader.php?sid=attack&user2ID={user.get('player_id')}) - {reward} "
                f"{user.get('status', {}).get('description')} ({bts_percentage}%)\n"
            )

        message += "\n\nupdated: " + time.strftime('%H:%M:%S', time.localtime())

        await chat_message.edit_text(
            telegramify_markdown.markdownify(message),
            parse_mode="MarkdownV2"
        )

        await asyncio.sleep(60)


async def watch_player_bounty(torn: Torn, player_info: Dict[str, Any], limit: int = 60) -> None:
    now = time.time()
    hospital = player_info.get("states", {}).get("hospital_timestamp", now)

    wait_time = hospital - now - limit
    if wait_time > 0:
        await asyncio.sleep(wait_time)

    user_info = await torn.get_basic_user(player_info.get("player_id"))
    if not user_info:
        return

    basicicons = user_info.get("basicicons", {})
    if basicicons.get("icon13") is None:
        return

    new_hospital = user_info.get("states", {}).get("hospital_timestamp")
    if new_hospital and new_hospital != hospital:
        player_info["states"] = user_info.get("states", {})
        await watch_player_bounty(torn, player_info, limit=limit)
        return

    reward = "${:,.0f}".format(player_info.get("reward", 0))
    try:
        message = await torn.send(
            f"{user_info.get('name')} is about to leave hospital with a bounty of {reward}. "
            f"[Attack](https://www.torn.com/loader.php?sid=attack&user2ID={player_info.get('player_id')})",
            clean=False
        )
    except Exception as exc:
        logger.error("Failed to send bounty notification: %s", exc)
        return

    await asyncio.sleep(max(limit, 0))

    try:
        await message.delete()
    except Exception as exc:
        logger.error("Failed to delete bounty notification: %s", exc)
